from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from ai import generar_receta
from usuarios import get_nombre
from whatsapp import reply_whatsapp, enviar_botones
import requests
import os

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

        # ✅ Filtrar solo los productos del supermercado elegido
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
            "productos": productos_final,   # ✅ solo del super elegido
        }

        print("📤 Enviando pedido:", pedido_data)  # debug

        response = requests.post(API_URL_PEDIDOS, json=pedido_data)

        if response.status_code in [200, 201]:
            total = sum(p["precio_total"] for p in productos_final)
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
    print("📩 Mensaje recibido:", data)

    try:
        entry = data["entry"][0]["changes"][0]["value"]

        # ✅ Caso 1: mensaje de texto normal
        if "messages" in entry:
            message = entry["messages"][0]
            from_number = message["from"]
            profile_name = entry["contacts"][0]["profile"]["name"]
            
            if message["type"] == "text":
                text = message["text"]["body"]

                # Generar receta
                receta, productos = generar_receta(profile_name, text, return_productos=True)

                # Guardar productos en sesión
                user_sessions[from_number] = {
                    "nombre": profile_name,
                    "productos": productos
                }

                # Responder receta
                reply_whatsapp(from_number, receta)

                # Enviar botones
                enviar_botones(from_number, "¿Querés hacer el pedido en Disco o Tienda Inglesa?")

            # ✅ Caso 2: usuario aprieta un botón
            elif message["type"] == "interactive":
                button_id = message["interactive"]["button_reply"]["id"]
                session = user_sessions.get(from_number)

                if session:
                    productos = session["productos"]
                    usuario = session["nombre"]

                    # ✅ Filtrar productos según el botón
                    if button_id == "disco":
                        productos_final = productos.get("disco", [])
                    elif button_id == "tienda_inglesa":
                        productos_final = productos.get("tienda_inglesa", [])
                    else:
                        productos_final = []

                    if productos_final:
                        pedido_data = {
                            "supermercado": button_id,
                            "usuario": usuario,
                            "productos": productos_final
                        }
                        print("📤 Enviando pedido (botón):", pedido_data)

                        response = requests.post(API_URL_PEDIDOS, json=pedido_data)

                        if response.status_code in [200, 201]:
                            reply_whatsapp(from_number, f"✅ Pedido enviado a {button_id}, {usuario}!")
                        else:
                            reply_whatsapp(from_number, "❌ Error al enviar el pedido")
                    else:
                        reply_whatsapp(from_number, "⚠️ No encontré productos para este supermercado")

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
