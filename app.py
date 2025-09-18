from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from ai import generar_receta
from usuarios import get_nombre
import requests

app = FastAPI(title="Chef Virtual API", version="2.0.0")

# ==========================
# CORS
# ==========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ en producción limitar a tu dominio frontend
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

@app.get("/")
async def read_index():
    """Sirve la interfaz web"""
    return FileResponse("index.html")

@app.post("/generate-recipe")
async def generate_recipe(request: RecipeRequest):
    """
    Genera receta con IA y devuelve:
    - Texto amigable
    - Lista de productos JSON estructurados
    """
    try:
        nombre = get_nombre(request.numero, request.nombre)
        receta, productos = generar_receta(nombre, request.mensaje, return_productos=True)

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
    """
    Procesa un pedido con los productos JSON y lo envía a la API de pedidos.
    Solo manda los productos del supermercado elegido.
    """
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

        response = requests.post("http://127.0.0.1:5001/pedidos", json=pedido_data)

        if response.status_code == 201:
            total = sum(p["precio_total"] for p in productos_final)
            return {
                "success": True,
                "message": "Pedido enviado correctamente",
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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Chef Virtual API"}

if __name__ == "__main__":
    import uvicorn
    print("🍳 Iniciando Chef Virtual API...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
