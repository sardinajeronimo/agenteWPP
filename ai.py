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


def limpiar_ingrediente(ingrediente):
    """Limpia el ingrediente para mejor matching"""
    original = ingrediente
    
   
    ingrediente = re.sub(r'\([^)]*\)', '', ingrediente)
    
  
    ingrediente = re.sub(r'\d+(?:[.,]\d+)?', '', ingrediente)
    ingrediente = re.sub(r'\d+/\d+', '', ingrediente)
    ingrediente = re.sub(r'/\d+', '', ingrediente)

    medidas = ['taza', 'tazas', 'cucharadita', 'cucharaditas', 'cucharada', 'cucharadas',
               'kg', 'gr', 'g', 'gramos', 'litro', 'litros', 'ml', 'cc', 'pizca',
               'paquete', 'lata', 'sobre', 'unidad', 'unidades', 'docena', 'opcional']
    
    for medida in medidas:
        ingrediente = re.sub(rf'\b{medida}s?\b', '', ingrediente, flags=re.IGNORECASE)
    
  
    conectores = ['de', 'del', 'la', 'el', 'en', 'con', 'sin', 'para', 'y', 'al', 'gusto', 
                  'tibia', 'fría', 'caliente', 'fresco', 'seco', 'líquido', 'polvo']
    for conector in conectores:
        ingrediente = re.sub(rf'\b{conector}\b', '', ingrediente, flags=re.IGNORECASE)
    

    ingrediente = re.sub(r'[/\\(),-]', '', ingrediente)
    
    
    ingrediente = re.sub(r'\s+', ' ', ingrediente).strip()
    
  
    if len(ingrediente) < 3:
        ingrediente = ""
    
    print(f"🧹 Limpieza: '{original}' → '{ingrediente}'")
    return ingrediente


def buscar_por_categoria(ingrediente, productos):
    """Busca productos por categorías específicas con lógica MUY estricta"""
    ingrediente_lower = ingrediente.lower().strip()
    
    if not ingrediente_lower or len(ingrediente_lower) < 3:
        print(f"❌ Ingrediente muy corto: '{ingrediente_lower}'")
        return None
    
    print(f"🔍 Buscando por categoría: '{ingrediente_lower}'")
    
 
    mapeos_exactos = {
        'mantequilla': 'manteca',
        'manteca': 'manteca',
        'azucar': 'azucar',
        'azúcar': 'azucar', 
        'huevos': 'huevos colorados', 
        'huevo': 'huevos colorados',
        'cacao': 'cocoa',
        'harina': 'harina de trigo',  
        'sal': 'sal',
        'levadura': 'levadura',
        'vainilla': 'vainilla',
        'esencia vainilla': 'vainilla',
        'leche': 'leche',
        'aceite oliva': 'aceite oliva',
        'aceite': 'aceite',
        'tomate': 'tomate',
        'cebolla': 'cebolla',
        'pimiento': 'pimiento',
        'carne': 'carne',
        'laurel': 'laurel',
        'caldo': 'caldo',
        'bicarbonato': 'bicarbonato'
    }
    
   
    palabra_buscar = None
    for clave, valor in mapeos_exactos.items():
        if ingrediente_lower == clave:
            palabra_buscar = valor
            break
    
    if not palabra_buscar:
        print(f"❌ No hay mapeo exacto para: '{ingrediente_lower}'")
        return None

    productos_candidatos = []
    for p in productos:
        nombre_lower = p["nombre_producto"].lower()
       
        if palabra_buscar == 'huevos colorados':
            if 'huevos colorados' in nombre_lower or 'huevo colorado' in nombre_lower:
                productos_candidatos.append(p)

        elif palabra_buscar == 'harina de trigo':
            if ('harina' in nombre_lower and 'trigo' in nombre_lower) or ('harina común' in nombre_lower):
                productos_candidatos.append(p)
    
        elif palabra_buscar == 'aceite oliva':
            if 'aceite' in nombre_lower and 'oliva' in nombre_lower:
                productos_candidatos.append(p)
    
        else:
            if palabra_buscar in nombre_lower:
                productos_candidatos.append(p)
    
    if not productos_candidatos:
        print(f"❌ No se encontraron productos para: '{palabra_buscar}'")
        return None
    
   
    producto = productos_candidatos[0]
    
    precios_disco = [
        p for p in productos_candidatos
        if p.get("supermercado", "").lower() == "disco"
    ]
    precios_ti = [
        p for p in productos_candidatos
        if p.get("supermercado", "").lower() == "tienda inglesa"
    ]
    
    print(f"✅ Match por categoría: '{ingrediente_lower}' → '{producto['nombre_producto']}'")
    
    return {
        "nombre": producto["nombre_producto"],
        "disco": precios_disco[0]["precio"] if precios_disco else None,
        "tienda_inglesa": precios_ti[0]["precio"] if precios_ti else None,
        "producto_id_disco": precios_disco[0].get("id") if precios_disco else None,
        "producto_id_ti": precios_ti[0].get("id") if precios_ti else None
    }


def buscar_precio_producto(ingrediente, productos):
    """Busca precios con fuzzy match mejorado"""
    try:
        if not productos:
            print("❌ No hay productos disponibles")
            return None

       
        productos_validos = [
            p for p in productos
            if "nombre_producto" in p
            and not any(
                kw in p["nombre_producto"].lower()
                for kw in ["jabon", "detergente", "repelente", "hipoclorito",
                           "lavandina", "pañal", "shampoo", "talco", "off"]
            )
        ]

        if not productos_validos:
            print("❌ No hay productos válidos (alimentos)")
            return None

        print(f"🔍 Buscando precio para: '{ingrediente}'")
        
     
        ingrediente_limpio = limpiar_ingrediente(ingrediente)
        
        
        if len(ingrediente_limpio.strip()) < 3:
            print(f"⚠️ Ingrediente muy corto después de limpiar: '{ingrediente_limpio}'")
            return None
        

        resultado = buscar_por_categoria(ingrediente_limpio, productos_validos)
        if resultado:
            return resultado
        
        
        nombres = [p["nombre_producto"] for p in productos_validos]
        resultado_fuzzy = process.extractOne(
            ingrediente_limpio.lower(),
            [n.lower() for n in nombres]
        )
        
        if not resultado_fuzzy:
            print(f"❌ No se encontró resultado fuzzy para: '{ingrediente_limpio}'")
            return None
            
        mejor, score, idx = resultado_fuzzy
 
        if score < 90:
            print(f"⚠️ Score muy bajo para '{ingrediente}' → '{nombres[idx]}' (score: {score})")
            return None

        producto_encontrado = nombres[idx]
        print(f"✅ Match fuzzy: '{ingrediente}' → '{producto_encontrado}' (score: {score})")


        precios_disco = [
            p for p in productos_validos
            if p["nombre_producto"].lower() == producto_encontrado.lower()
            and p.get("supermercado", "").lower() == "disco"
        ]
        precios_ti = [
            p for p in productos_validos
            if p["nombre_producto"].lower() == producto_encontrado.lower()
            and p.get("supermercado", "").lower() == "tienda inglesa"
        ]

        
        if precios_disco:
            print(f"💰 Disco: {precios_disco[0]['precio']} (ID: {precios_disco[0].get('id')})")
        if precios_ti:
            print(f"💰 TI: {precios_ti[0]['precio']} (ID: {precios_ti[0].get('id')})")

        return {
            "nombre": producto_encontrado,
            "disco": precios_disco[0]["precio"] if precios_disco else None,
            "tienda_inglesa": precios_ti[0]["precio"] if precios_ti else None,
            "producto_id_disco": precios_disco[0].get("id") if precios_disco else None,
            "producto_id_ti": precios_ti[0].get("id") if precios_ti else None
        }

    except Exception as e:
        print(f"⚠️ Error en fuzzy match: {e}")
    return None


def calcular_unidades(cantidad: float, medida: str, producto_nombre: str):
    """Ajusta la cantidad según la presentación del producto"""
    match = re.search(r"\(([^)]+)\)", producto_nombre.lower())
    if not match:
        return 1, int(math.ceil(cantidad))

    presentacion = match.group(1)
    print(f"📦 Calculando unidades para {cantidad} {medida} en presentación '{presentacion}'")

    
    if "docena" in presentacion:
        if "1/2" in presentacion:
            pack_size = 6
        else:
            pack_size = 12
        unidades = math.ceil(cantidad / pack_size)
        print(f"🥚 Huevos: {cantidad} → {unidades} paquetes de {pack_size}")
        return pack_size, unidades

    
    if "kg" in presentacion:
        num = re.search(r"(\d+(?:[.,]\d+)?)", presentacion)
        pack_size = float(num.group(1).replace(",", ".")) * 1000 if num else 1000
        if medida in ["kg", "g", "gramos"]:
            cantidad_g = cantidad * (1000 if medida == "kg" else 1)
            unidades = math.ceil(cantidad_g / pack_size)
        else:
            unidades = 1
        return pack_size, unidades


    if "gr" in presentacion:
        num = re.search(r"(\d+(?:[.,]\d+)?)", presentacion)
        pack_size = float(num.group(1).replace(",", ".")) if num else 500
        if medida in ["g", "gramos"]:
            unidades = math.ceil(cantidad / pack_size)
        else:
            unidades = 1
        return pack_size, unidades

    return 1, int(math.ceil(cantidad))


def eliminar_duplicados(productos_pedido):
    """Elimina productos duplicados del pedido"""
    print("🔄 Eliminando duplicados...")
    for supermercado in productos_pedido:
        productos_unicos = {}
        
        for producto in productos_pedido[supermercado]:
            nombre = producto["nombre"]
            if nombre in productos_unicos:
                print(f"🔄 Consolidando duplicado: {nombre}")
                productos_unicos[nombre]["cantidad"] += producto["cantidad"]
                productos_unicos[nombre]["precio_total"] = (
                    productos_unicos[nombre]["precio_unitario"] * 
                    productos_unicos[nombre]["cantidad"]
                )
            else:
                productos_unicos[nombre] = producto
        
        productos_pedido[supermercado] = list(productos_unicos.values())
        print(f"✅ {supermercado}: {len(productos_unicos)} productos únicos")
    
    return productos_pedido


def enviar_pedido(supermercado, productos_pedido, usuario_numero):
    """Envía el pedido con debugging completo"""
    try:
        print(f"\n📤 ENVIANDO PEDIDO A {supermercado.upper()}")
        print(f"👤 Usuario: {usuario_numero}")
        
        supermercado_key = "disco" if supermercado.lower() == "disco" else "tienda_inglesa"
        productos_lista = productos_pedido.get(supermercado_key, [])
        
        if not productos_lista:
            print(f"❌ No hay productos para {supermercado}")
            return f"❌ No hay productos para enviar a {supermercado}"
        
        productos_para_enviar = []
        
        for i, producto in enumerate(productos_lista):
            print(f"\n📦 Producto {i+1}:")
            print(f"   Nombre: {producto['nombre']}")
            print(f"   Cantidad: {producto['cantidad']}")
            print(f"   Precio unitario: ${producto['precio_unitario']}")
            print(f"   Precio total: ${producto['precio_total']}")
            
    
            if supermercado.lower() == "disco":
                producto_id = producto.get("producto_id_disco")
                print(f"   ID Disco: {producto_id}")
            else:
                producto_id = producto.get("producto_id_ti")
                print(f"   ID TI: {producto_id}")
            
            productos_para_enviar.append({
                "producto_id": str(producto_id) if producto_id else "",
                "nombre": producto["nombre"],
                "precio_unitario": float(producto["precio_unitario"]),
                "cantidad": int(producto["cantidad"]),
                "precio_total": float(producto["precio_total"])
            })
        
        total = sum(p["precio_total"] for p in productos_para_enviar)
        
        pedido_data = {
            "usuario_numero": str(usuario_numero),
            "supermercado": supermercado.lower(),
            "productos": productos_para_enviar,
            "total": total
        }
        
        print(f"\n📋 DATOS DEL PEDIDO:")
        print(f"   Usuario: {pedido_data['usuario_numero']}")
        print(f"   Supermercado: {pedido_data['supermercado']}")
        print(f"   Total productos: {len(productos_para_enviar)}")
        print(f"   Total: ${total}")
        
        print(f"\n🚀 Enviando POST a: {API_URL_PEDIDOS}")
        response = requests.post(API_URL_PEDIDOS, json=pedido_data, timeout=10)
        
        print(f"📡 Respuesta HTTP: {response.status_code}")
        if response.text:
            print(f"📄 Respuesta: {response.text}")
        
        if response.status_code == 200:
            return f"✅ Pedido enviado a {supermercado}. Total: ${total:.2f}"
        else:
            return f"❌ Error enviando pedido: HTTP {response.status_code}"
            
    except Exception as e:
        print(f"💥 Error enviando pedido: {str(e)}")
        return f"❌ Error enviando pedido: {str(e)}"


def generar_receta(nombre: str, user_msg: str, usuario_numero=None, return_productos=False):
    """Genera receta con debugging completo"""
    print(f"\n🍳 GENERANDO RECETA PARA: {nombre}")
    print(f"📝 Solicitud: {user_msg}")
    

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""
Eres un chef experto y cercano que responde con recetas claras y fáciles de seguir.
Siempre saluda al usuario por su nombre ({nombre}) de manera amigable.

**Formato de tu respuesta:**
1. Título con el nombre de la receta.
2. Sección "Ingredientes" → lista los ingredientes de manera simple.
3. Sección "Preparación" → pasos numerados, cortos y prácticos.
"""
                },
                {"role": "user", "content": user_msg}
            ]
        )
        receta_base = completion.choices[0].message.content.strip()
        print("✅ Receta generada con IA")
    except Exception as e:
        print(f"❌ Error generando receta: {e}")
        receta_base = f"⚠️ Error generando receta con IA: {str(e)}"
        if return_productos:
            return receta_base, {"disco": [], "tienda_inglesa": []}
        return receta_base


    productos = obtener_productos()
    if not productos:
        print("❌ No se pudieron cargar productos")
        if return_productos:
            return receta_base, {"disco": [], "tienda_inglesa": []}
        return receta_base

    
    ingredientes = []
    try:
        lineas = receta_base.splitlines()
        en_ingredientes = False

        for linea in lineas:
            linea_lower = linea.lower().strip()
            if "ingredientes" in linea_lower and not en_ingredientes:
                en_ingredientes = True
                continue
            if any(p in linea_lower for p in ["preparación", "preparacion", "instrucciones", "pasos"]):
                en_ingredientes = False
            if en_ingredientes and linea.strip() and linea.strip().startswith(("-", "•")):
                ingrediente_limpio = linea.strip().lstrip("- •").strip()
                if ingrediente_limpio:
                    ingredientes.append(ingrediente_limpio)
                    
        print(f" Ingredientes extraídos: {len(ingredientes)}")
        for i, ing in enumerate(ingredientes, 1):
            print(f"   {i}. {ing}")
            
    except Exception as e:
        print(f"❌ Error extrayendo ingredientes: {e}")


    productos_pedido = {"disco": [], "tienda_inglesa": []}
    precios_texto = []
    total_disco = 0
    total_ti = 0

    print(f"\n💰 BUSCANDO PRECIOS...")
    for i, ingrediente_completo in enumerate(ingredientes, 1):
        print(f"\n--- INGREDIENTE {i}/{len(ingredientes)} ---")
        print(f"🔍 Procesando: '{ingrediente_completo}'")
        
        try:
            resultado = buscar_precio_producto(ingrediente_completo, productos)
            if resultado:
                cantidad_match = re.search(r'(\d+(?:[.,]\d+)?)', ingrediente_completo)
                cantidad = float(cantidad_match.group(1).replace(",", ".")) if cantidad_match else 1

                medida_match = re.search(r'(kg|gr|g|litro|lt|l|ml|cc|unidad|unidades|docena|pizca|taza|cucharada|cucharadita)', ingrediente_completo.lower())
                medida = medida_match.group(1) if medida_match else "unidad"

                pack_size, unidades = calcular_unidades(cantidad, medida, resultado["nombre"])

                if resultado["disco"] is not None:
                    productos_pedido["disco"].append({
                        "nombre": resultado["nombre"],
                        "precio_unitario": float(resultado["disco"]),
                        "presentacion": pack_size,
                        "cantidad": unidades,
                        "precio_total": float(resultado["disco"]) * unidades,
                        "producto_id_disco": resultado.get("producto_id_disco")
                    })
                    total_disco += float(resultado["disco"]) * unidades

                if resultado["tienda_inglesa"] is not None:
                    productos_pedido["tienda_inglesa"].append({
                        "nombre": resultado["nombre"],
                        "precio_unitario": float(resultado["tienda_inglesa"]),
                        "presentacion": pack_size,
                        "cantidad": unidades,
                        "precio_total": float(resultado["tienda_inglesa"]) * unidades,
                        "producto_id_ti": resultado.get("producto_id_ti")
                    })
                    total_ti += float(resultado["tienda_inglesa"]) * unidades

                disco_str = f"{unidades} x ${resultado['disco']} = ${float(resultado['disco'])*unidades:.2f}" if resultado["disco"] else "sin precio"
                ti_str = f"{unidades} x ${resultado['tienda_inglesa']} = ${float(resultado['tienda_inglesa'])*unidades:.2f}" if resultado["tienda_inglesa"] else "sin precio"

                precios_texto.append(
                    f"- {ingrediente_completo}: {disco_str} (Disco) / {ti_str} (Tienda Inglesa)"
                )
                print(f"✅ Precios agregados")
            else:
                print(f"❌ No se encontró precio")

        except Exception as e:
            print(f"💥 Error procesando ingrediente: {e}")
            continue

    productos_pedido = eliminar_duplicados(productos_pedido)


    respuesta_final = f"👨‍🍳 Receta para {nombre}\n\n{receta_base}"
    if precios_texto:
        respuesta_final += f"\n\n**Precios disponibles:**\n" + "\n".join(precios_texto)
        respuesta_final += f"\n\n**Total Disco:** ${total_disco:.2f}"
        respuesta_final += f"\n**Total Tienda Inglesa:** ${total_ti:.2f}"
        respuesta_final += f"\n¿Querés hacer el pedido? Escribí 'tienda inglesa' o 'disco'."
    else:
        respuesta_final += f"\n\n*(No se encontraron precios para los ingredientes en nuestra base de datos)*"

    print(f"\n✅ RECETA GENERADA")
    print(f"   Disco: {len(productos_pedido['disco'])} productos, ${total_disco}")
    print(f"   TI: {len(productos_pedido['tienda_inglesa'])} productos, ${total_ti}")

    if return_productos:
        return respuesta_final, productos_pedido
    return respuesta_final