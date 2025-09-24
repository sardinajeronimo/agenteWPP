from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from ai import generar_receta
from usuarios import get_nombre
from whatsapp import reply_whatsapp, enviar_botones
import requests
import os, json


app = FastAPI(title="Chef Virtual API", version="3.0.0")

# ==========================
# CORS
# ==========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ limitar en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# MODELOS DE REQUEST
# ==========================
class RecipeRequest(BaseModel):
    nombre: str
    mensaje: str
    numero: str

class OrderRequest(BaseModel):
    supermercado: str
    usuario: str
    productos: dict 

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "mitokenverificacion")
API_URL_PEDIDOS = os.getenv("API_URL_PEDIDOS", "http://127.0.0.1:5001/pedidos")

# 🔹 memoria temporal para guardar productos por usuario
user_sessions = {}

# ==========================
# RUTAS WEB
# ==========================
@app.get("/")
async def read_index():
    return FileResponse("index.html")

@app.post("/generate-recipe")
async def generate_recipe(request: RecipeRequest):
    try:
        nombre = get_nombre(request.numero, request.nombre)
        receta, productos = generar_receta(nombre, request.mensaje, return_productos=True)

        # guardar productos en sesión
        user_sessions[request.numero] = {
            "nombre": nombre,
            "productos": productos
        }

        return {
            "success": True,
            "receta": receta,
            "productos": productos,
            "usuario": nombre
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando receta: {str(e)}")

@app.post("/make-order")
async def make_order(request: OrderRequest):
    try:
        supermercado = request.supermercado.lower()

        if supermercado == "disco":
            productos_final = request.productos.get("disco", [])
        elif supermercado == "tienda inglesa":
            productos_final = request.productos.get("tienda_inglesa", [])
        else:
            raise HTTPException(status_code=400, detail="Supermercado no válido")

        if not productos_final:
            raise HTTPException(status_code=400, detail="No hay productos en el pedido para este supermercado")

        pedido_data = {
            "usuario": request.usuario,
            "supermercado": supermercado,
            "productos": productos_final,
        }

        print("📤 Enviando pedido:", pedido_data)

        response = requests.post(API_URL_PEDIDOS, json=pedido_data)

        if response.status_code in [200, 201]:
            total = sum(p["precio_total"] for p in productos_final)

            # ✅ Guardar confirmados en la sesión
            user_sessions[request.usuario] = {
                "nombre": request.usuario,
                "productos": {supermercado: productos_final},
                "confirmados": {supermercado: productos_final}
            }

            return {
                "success": True,
                "message": f"Pedido enviado correctamente a {supermercado}",
                "productos": productos_final,
                "total": round(total, 2),
                "supermercado": supermercado
            }
        else:
            raise HTTPException(status_code=500, detail="Error enviando pedido a la API")

    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Error de conexión con la API de pedidos")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando pedido: {str(e)}")

# ==========================
# WHATSAPP WEBHOOK
# ==========================
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if token == VERIFY_TOKEN:
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Token inválido")
    raise HTTPException(status_code=400, detail="Error en verificación")

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print("📩 Payload recibido:", json.dumps(data, indent=2, ensure_ascii=False))

    try:
        entry = data.get("entry", [])[0].get("changes", [])[0].get("value", {})

        if "messages" in entry:
            message = entry["messages"][0]
            from_number = message.get("from")
            profile_name = entry.get("contacts", [{}])[0].get("profile", {}).get("name", "Usuario")

            # 📝 Texto
            if message.get("type") == "text":
                text = message["text"].get("body", "").strip().lower()
                print(f"👤 {profile_name} ({from_number}) dijo: {text}")

                saludos = ["hola", "buenas", "qué tal", "buen día", "buenas tardes", "buenas noches"]
                if text in saludos:
                    reply_whatsapp(from_number, f"👋 Hola {profile_name}! Soy tu Chef Virtual 🤖🍳. Pedime una receta y te ayudo.")
                    return {"status": "ok"}

                if text == "cancelar":
                    user_sessions.pop(from_number, None)
                    reply_whatsapp(from_number, "❌ Pedido cancelado. Podés pedirme otra receta cuando quieras.")
                    return {"status": "ok"}

                receta, productos = generar_receta(profile_name, text, return_productos=True)
                user_sessions[from_number] = {"nombre": profile_name, "productos": productos}
                reply_whatsapp(from_number, receta)
                enviar_botones(from_number, "¿Querés hacer el pedido ahora?")

            elif message.get("type") == "interactive":
                button_id = message["interactive"]["button_reply"]["id"]
                session = user_sessions.get(from_number)

                if not session:
                    reply_whatsapp(from_number, "⚠️ No tengo productos guardados para tu sesión. Pedime una receta primero.")
                    return {"status": "ok"}

                productos = session["productos"]
                usuario = session["nombre"]

                if button_id == "listar":
                    if "confirmados" not in session:
                        reply_whatsapp(from_number, "⚠️ Aún no hiciste un pedido, no hay nada para listar.")
                        return {"status": "ok"}

                    listado = []
                    for super, items in session["confirmados"].items():
                        listado.append(f"🏪 {super.upper()}:")
                        for p in items:
                            listado.append(f" - {p['nombre']} ({p['cantidad']}) (${p['precio_total']})")
                    reply_whatsapp(from_number, "\n".join(listado))
                    return {"status": "ok"}

                elif button_id in ["disco", "tienda_inglesa"]:
                    productos_final = productos.get(button_id, [])
                    if productos_final:
                        pedido_data = {
                            "supermercado": button_id,
                            "usuario": usuario,
                            "productos": productos_final
                        }
                        print("📤 Enviando pedido (botón):", pedido_data)
                        response = requests.post(API_URL_PEDIDOS, json=pedido_data)

                        if response.status_code in [200, 201]:
                            # ✅ Guardamos confirmados
                            session["confirmados"] = {button_id: productos_final}
                            reply_whatsapp(from_number, f"✅ Pedido enviado a {button_id}, {usuario}!")
                        else:
                            reply_whatsapp(from_number, "❌ Error al enviar el pedido")
                    else:
                        reply_whatsapp(from_number, "⚠️ No encontré productos para este supermercado")

        elif "statuses" in entry:
            print("ℹ️ Evento de estado:", json.dumps(entry["statuses"], indent=2, ensure_ascii=False))

        else:
            print("⚠️ Evento no reconocido:", json.dumps(entry, indent=2, ensure_ascii=False))

    except Exception as e:
        print("⚠️ Error procesando webhook:", e)

    return {"status": "ok"}

# ==========================
# HEALTH CHECK
# ==========================
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Chef Virtual API"}

if __name__ == "__main__":
    import uvicorn
    print(" Iniciando Chef Virtual API...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
