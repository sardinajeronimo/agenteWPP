from rapidfuzz import fuzz
import requests

def procesar_pedido(from_number: str):
    """
    Procesa el pedido de un usuario:
    1. Obtiene productos desde una API o base de datos.
    2. Hace fuzzy match entre los ingredientes de la receta y los productos.
    3. Devuelve un JSON con la selección de productos.
    """

    try:
        productos = requests.get("http://localhost:5000/productos").json()
    except Exception as e:
        print("Error obteniendo productos:", e)
        return {"error": "No se pudo obtener productos"}

    ingredientes = ["arroz", "pollo", "cebolla"]

    resultado = {"productos": []}
    for ing in ingredientes:
        mejor = max(productos, key=lambda p: fuzz.partial_ratio(ing, p["nombre_producto"]))
        resultado["productos"].append({
            "ingrediente": ing,
            "producto": mejor["nombre_producto"],
            "precio": mejor["precio"],
            "supermercado": mejor["supermercado"]
        })


    print(f"Pedido procesado para {from_number}: {resultado}")
    return resultado
