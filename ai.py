from openai import OpenAI
import os
import requests
from dotenv import load_dotenv
from rapidfuzz import process
import re
import math

load_dotenv()

API_URL_PRODUCTOS = os.getenv("API_URL_PRODUCTOS", "http://127.0.0.1:5003/productos")
API_URL_PEDIDOS = os.getenv("API_URL_PEDIDOS", "http://127.0.0.1:5001/pedidos")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

productos_debug = []


def obtener_productos():
    global productos_debug
    try:
        resp = requests.get(API_URL_PRODUCTOS, timeout=5)
        if resp.status_code == 200:
            productos_debug = resp.json()
            print(f"📦 Cargados {len(productos_debug)} productos")
            return productos_debug
    except Exception as e:
        print(f"⚠️ Error obteniendo productos: {e}")
    return []


def limpiar_ingrediente(ingrediente: str) -> str:
    """Limpia un ingrediente para mejor matching"""
    original = ingrediente
    ingrediente = re.sub(r'\([^)]*\)', '', ingrediente)
    ingrediente = re.sub(r'\d+(?:[.,]\d+)?', '', ingrediente)
    ingrediente = re.sub(r'\d+/\d+', '', ingrediente)

    medidas = [
        'taza', 'tazas', 'cucharadita', 'cucharaditas', 'cucharada', 'cucharadas',
        'kg', 'gr', 'g', 'gramos', 'litro', 'litros', 'ml', 'cc', 'pizca',
        'paquete', 'lata', 'sobre', 'unidad', 'unidades', 'docena', 'opcional'
    ]
    for m in medidas:
        ingrediente = re.sub(rf'\b{m}s?\b', '', ingrediente, flags=re.IGNORECASE)

    conectores = [
        'de', 'del', 'la', 'el', 'en', 'con', 'sin', 'para', 'y', 'al',
        'gusto', 'tibia', 'fría', 'frio', 'caliente', 'fresco', 'seco',
        'líquido', 'polvo'
    ]
    for c in conectores:
        ingrediente = re.sub(rf'\b{c}\b', '', ingrediente, flags=re.IGNORECASE)

    ingrediente = re.sub(r'[/\\(),\s-]+', ' ', ingrediente).strip()
    if len(ingrediente) < 3:
        ingrediente = ""

    print(f"🧹 Limpieza: '{original}' → '{ingrediente}'")
    return ingrediente


def buscar_por_categoria(ingrediente, productos):
    ingrediente_lower = ingrediente.lower().strip()
    mapeos_exactos = {
        'mantequilla': 'manteca',
        'manteca': 'manteca',
        'azucar': 'azucar',
        'azúcar': 'azucar',
        'huevos': 'huevos colorados',
        'huevo': 'huevos colorados',
        'harina': 'harina de trigo',
        'sal': 'sal',
        'levadura': 'levadura',
        'vainilla': 'vainilla',
        'leche': 'leche',
        'aceite oliva': 'aceite oliva',
        'aceite': 'aceite',
        'tomate': 'tomate',
        'cebolla': 'cebolla',
        'pimiento': 'pimiento',
        'carne': 'carne',
        'cacao': 'cocoa',
    }

    palabra_buscar = mapeos_exactos.get(ingrediente_lower)
    if not palabra_buscar:
        return None

    candidatos = [p for p in productos if palabra_buscar in p["nombre_producto"].lower()]
    if not candidatos:
        return None

    precios_disco = [p for p in candidatos if p.get("supermercado", "").lower() == "disco"]
    precios_ti = [p for p in candidatos if p.get("supermercado", "").lower() == "tienda inglesa"]

    return {
        "nombre": candidatos[0]["nombre_producto"],
        "disco": precios_disco[0]["precio"] if precios_disco else None,
        "tienda_inglesa": precios_ti[0]["precio"] if precios_ti else None,
        "producto_id_disco": precios_disco[0].get("id") if precios_disco else None,
        "producto_id_ti": precios_ti[0].get("id") if precios_ti else None
    }


def es_no_comestible(nombre: str) -> bool:
    """Detecta si un producto no es comestible por su nombre"""
    nombre = nombre.lower()

    # Lista de palabras clave a descartar (puede expandirse según lo que veas en la API)
    blacklist = [
        "jabon", "jabón", "detergente", "repelente", "hipoclorito", "lavandina",
        "pañal", "pañales", "shampoo", "champu", "champú", "talco", "off",
        "desodorante", "ambientador", "limpiador", "lavavajilla", "suavizante",
        "perfume", "cera", "insecticida", "foco", "velas", "toallas", "servilleta",
        "pañuelo", "pasta dental", "pasta de dientes", "colgate", "oral b", "cepillo"
    ]

    return any(kw in nombre for kw in blacklist)


def buscar_precio_producto(ingrediente, productos):
    """Busca un producto con fuzzy matching + categorías"""
    try:
        if not productos:
            return None

        # ✅ Filtrar no comestibles con la función
        productos_validos = [
            p for p in productos
            if "nombre_producto" in p and not es_no_comestible(p["nombre_producto"])
        ]

        if not productos_validos:
            return None

        ingrediente_limpio = limpiar_ingrediente(ingrediente)
        if len(ingrediente_limpio) < 3:
            return None

        # 1. Match por categoría fija
        resultado = buscar_por_categoria(ingrediente_limpio, productos_validos)
        if resultado:
            return resultado

        # 2. Fuzzy matching
        nombres = [p["nombre_producto"] for p in productos_validos]
        fuzzy = process.extractOne(ingrediente_limpio.lower(), [n.lower() for n in nombres])
        if not fuzzy:
            return None

        mejor, score, idx = fuzzy
        if score < 80:
            return None

        producto = productos_validos[idx]
        precios_disco = [
            p for p in productos_validos
            if p["nombre_producto"] == producto["nombre_producto"]
            and p["supermercado"].lower() == "disco"
        ]
        precios_ti = [
            p for p in productos_validos
            if p["nombre_producto"] == producto["nombre_producto"]
            and p["supermercado"].lower() == "tienda inglesa"
        ]

        return {
            "nombre": producto["nombre_producto"],
            "disco": precios_disco[0]["precio"] if precios_disco else None,
            "tienda_inglesa": precios_ti[0]["precio"] if precios_ti else None,
            "producto_id_disco": precios_disco[0].get("id") if precios_disco else None,
            "producto_id_ti": precios_ti[0].get("id") if precios_ti else None
        }

    except Exception as e:
        print(f"⚠️ Error en búsqueda: {e}")
        return None


def calcular_unidades(cantidad: float, medida: str, producto_nombre: str):
    # Captura presentaciones tipo: (400g), (400 g), (1 kg), (500 ml), (1/2 docena), (docena)
    m = re.search(r"\(([^)]+)\)", producto_nombre.lower())
    if not m:
        # ⚠️ Antes devolvía ceil(cantidad) -> eso generaba 400 x precio.
        return 1, 1

    presentacion = m.group(1)

    # DOCENA(S)
    if "docena" in presentacion:
        pack = 6 if "1/2" in presentacion else 12
        # si solo pedís 1 unidad (p.ej. 1 huevo), igual comprás el pack mínimo
        unidades = 1 if cantidad <= 1 else math.ceil(cantidad / pack)
        return pack, unidades

    # Extraer número de la presentación (400, 1, etc.)
    num = re.search(r"(\d+(?:[.,]\d+)?)", presentacion)
    valor = float(num.group(1).replace(",", ".")) if num else None
    if valor is None:
        return 1, 1  # si no pudimos leer el número, pedimos 1 unidad

    # Normalizar pack a gramos o mililitros donde aplique
    pack = None
    if "kg" in presentacion:
        pack = valor * 1000  # kg -> g
        unidad_receta_en_g = (cantidad * 1000) if medida == "kg" else cantidad
        unidades = 1 if pack >= unidad_receta_en_g else math.ceil(unidad_receta_en_g / pack)
        return pack, unidades

    if ("gr" in presentacion) or re.search(r"\b[g]\b", presentacion) or "gramo" in presentacion:
        pack = valor  # g
        # receta puede venir en kg o g
        unidad_receta_en_g = (cantidad * 1000) if medida == "kg" else cantidad
        unidades = 1 if pack >= unidad_receta_en_g else math.ceil(unidad_receta_en_g / pack)
        return pack, unidades

    if "l" in presentacion and "ml" not in presentacion:
        pack = valor * 1000  # l -> ml
        unidad_receta_en_ml = (cantidad * 1000) if medida in ["l", "lt"] else cantidad
        unidades = 1 if pack >= unidad_receta_en_ml else math.ceil(unidad_receta_en_ml / pack)
        return pack, unidades

    if ("ml" in presentacion) or ("cc" in presentacion):
        pack = valor  # ml
        unidad_receta_en_ml = (cantidad * 1000) if medida in ["l", "lt"] else cantidad
        unidades = 1 if pack >= unidad_receta_en_ml else math.ceil(unidad_receta_en_ml / pack)
        return pack, unidades

    # Por defecto (presentaciones como "(unidad)", "(frasco)", etc.)
    return 1, 1

def eliminar_duplicados(productos_pedido):
    for supermercado in productos_pedido:
        productos_unicos = {}
        for p in productos_pedido[supermercado]:
            if p["nombre"] in productos_unicos:
                productos_unicos[p["nombre"]]["cantidad"] += p["cantidad"]
                productos_unicos[p["nombre"]]["precio_total"] = (
                    productos_unicos[p["nombre"]]["cantidad"] *
                    productos_unicos[p["nombre"]]["precio_unitario"]
                )
            else:
                productos_unicos[p["nombre"]] = p
        productos_pedido[supermercado] = list(productos_unicos.values())
    return productos_pedido


def extraer_utiles_de_instrucciones(instrucciones_lines):
    texto = " ".join(instrucciones_lines).lower()
    patrones = {
        "bol": r"\b(bol|bowl|tazón|tazon)\b",
        "batidora": r"\b(batidora|batidor|gancho)\b",
        "molde": r"\b(molde|budinera|panera|tartera)\b",
        "horno": r"\bhorno\b",
        "sartén/olla": r"\b(sart[eé]n|olla|cacerola)\b",
        "rejilla": r"\brejilla\b",
        "rodillo": r"\b(rodillo|palo de amasar)\b",
        "espátula": r"\b(espatula|espátula|cuchara de madera)\b"
    }
    utiles = []
    for nombre, patron in patrones.items():
        if re.search(patron, texto):
            utiles.append(nombre)
    return utiles


def generar_receta(nombre: str, user_msg: str, usuario_numero=None, return_productos=False):
    print(f"\n🍳 GENERANDO RECETA PARA: {nombre}")
    print(f"📝 Solicitud: {user_msg}")

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"Eres un chef que responde con recetas claras y fáciles. Saluda siempre a {nombre}."},
                {"role": "user", "content": user_msg}
            ]
        )
        receta_base = completion.choices[0].message.content.strip()
        print("✅ Receta generada con IA")
    except Exception as e:
        receta_base = f"⚠️ Error generando receta con IA: {str(e)}"
        result = {
            "ingredientes": receta_base,
            "instrucciones": "",
            "precios": ""
        }
        if return_productos:
            return result, {"disco": [], "tienda_inglesa": []}
        return result

    productos = obtener_productos()
    if not productos:
        result = {
            "ingredientes": receta_base,
            "instrucciones": "",
            "precios": ""
        }
        if return_productos:
            return result, {"disco": [], "tienda_inglesa": []}
        return result

    ingredientes = []
    en_ing = False
    instrucciones_lines = []
    for linea in receta_base.splitlines():
        l = linea.lower().strip()
        if "ingredientes" in l and not en_ing:
            en_ing = True
            continue
        if any(p in l for p in ["preparación", "preparacion", "instrucciones", "pasos"]):
            en_ing = False
        if en_ing and linea.strip() and linea.strip().startswith(("-", "•")):
            ingredientes.append(linea.strip().lstrip("- •").strip())
        elif not en_ing and linea.strip():
            instrucciones_lines.append(linea)

    productos_pedido = {"disco": [], "tienda_inglesa": []}
    precios_texto, total_disco, total_ti = [], 0, 0

    for ing in ingredientes:
        res = buscar_precio_producto(ing, productos)
        if res:
            cant_match = re.search(r'(\d+(?:[.,]\d+)?)', ing)
            cantidad = float(cant_match.group(1).replace(",", ".")) if cant_match else 1
            med_match = re.search(r'(kg|gr|g|litro|lt|l|ml|cc|unidad|unidades|docena|pizca|taza|cucharada|cucharadita)', ing.lower())
            medida = med_match.group(1) if med_match else "unidad"
            pack, unidades = calcular_unidades(cantidad, medida, res["nombre"])

            if res["disco"]:
                productos_pedido["disco"].append({
                    "nombre": res["nombre"],
                    "precio_unitario": res["disco"],
                    "cantidad": unidades,
                    "precio_total": res["disco"] * unidades,
                    "producto_id_disco": res.get("producto_id_disco")
                })
                total_disco += res["disco"] * unidades
            if res["tienda_inglesa"]:
                productos_pedido["tienda_inglesa"].append({
                    "nombre": res["nombre"],
                    "precio_unitario": res["tienda_inglesa"],
                    "cantidad": unidades,
                    "precio_total": res["tienda_inglesa"] * unidades,
                    "producto_id_ti": res.get("producto_id_ti")
                })
                total_ti += res["tienda_inglesa"] * unidades

            disco_str = f"{unidades} x ${res['disco']} = ${res['disco']*unidades:.2f}" if res["disco"] else "sin precio"
            ti_str = f"{unidades} x ${res['tienda_inglesa']} = ${res['tienda_inglesa']*unidades:.2f}" if res["tienda_inglesa"] else "sin precio"
            precios_texto.append(f"- {ing}: {disco_str} (Disco) / {ti_str} (Tienda Inglesa)")

    productos_pedido = eliminar_duplicados(productos_pedido)

    ingredientes_text = f"👨‍🍳 Receta para {nombre}\n\n### Ingredientes:\n"
    ingredientes_text += "\n".join([f"• {ing}" for ing in ingredientes]) if ingredientes else "No se detectaron ingredientes."

    utiles_list = extraer_utiles_de_instrucciones(instrucciones_lines)
    utiles_text = ""
    if utiles_list:
        utiles_text = "### Útiles de cocina:\n" + "\n".join([f"• {u}" for u in utiles_list]) + "\n\n"

    instrucciones_text = utiles_text + "### Instrucciones:\n" + "\n".join(instrucciones_lines)

    precios_final = ""
    if precios_texto:
        precios_final = "\n💲 Precios disponibles:\n" + "\n".join(precios_texto)
        precios_final += f"\n\n👉 Total Disco: ${total_disco:.2f}\n👉 Total Tienda Inglesa: ${total_ti:.2f}"
        precios_final += "\n\n¿Querés hacer el pedido? Escribí 'tienda inglesa' o 'disco'."

    result = {
        "ingredientes": ingredientes_text,
        "instrucciones": instrucciones_text,
        "precios": precios_final
    }

    if return_productos:
        return result, productos_pedido
    return result
