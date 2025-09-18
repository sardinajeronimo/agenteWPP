from usuarios import get_nombre
from ai import generar_receta
import requests
import re

API_RECETAS = "http://127.0.0.1:5001/pedidos"  # Endpoint local

def enviar_pedido(supermercado, productos_pedido, usuario_numero):
    """
    Hace un POST a apiRecetas con el pedido en formato JSON.
    """
    pedido = {
        "usuario": usuario_numero,
        "supermercado": supermercado,
        "productos": productos_pedido,
        "timestamp": "2025-01-01T00:00:00Z"
    }

    try:
        resp = requests.post(API_RECETAS, json=pedido, timeout=5)
        if resp.status_code == 201:
            print(f"✅ Pedido enviado a {supermercado}:")
            print(resp.json())
            return True
        else:
            print(f"❌ Error al enviar pedido: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def mostrar_resumen_pedido(productos):
    """
    Muestra un resumen del pedido antes de enviarlo.
    """
    if not productos:
        print("⚠️ No hay productos en el pedido.")
        return

    print("\n📦 Resumen del pedido:")
    print("-" * 40)
    total = 0
    for producto in productos:
        try:
            subtotal = producto.get("precio", 0) * producto.get("cantidad", 1)
            total += subtotal
            print(f"• {producto.get('cantidad', 1)} x {producto.get('nombre', 'Producto desconocido')}")
            print(f"  ${producto.get('precio', 0)} c/u = ${subtotal:.2f}")
        except Exception:
            continue
    print("-" * 40)
    print(f"💰 TOTAL: ${total:.2f}")
    print()

def confirmar_pedido():
    """
    Pide confirmación al usuario antes de enviar el pedido.
    """
    while True:
        confirmar = input("🤖 ¿Confirmás el pedido? (s/n): ").strip().lower()
        if confirmar in ["s", "si", "sí", "y", "yes"]:
            return True
        elif confirmar in ["n", "no"]:
            return False
        else:
            print("⚠️ Respondé con 's' para sí o 'n' para no.")

def chatLocal():
    """
    Función principal del chat local.
    """
    fromNumber = "59893938387"
    nombreUsuario = "Jerónimo"
    nombreDef = get_nombre(fromNumber, nombreUsuario)

    print("🍳 ¡Bienvenido al Chef Virtual!")
    print(f"👋 Hola {nombreDef}!")
    print("💬 Chat iniciado. Pedí una receta para comenzar.")
    print("✏️ Escribí 'salir' para terminar.\n")

    while True:
        msg = input("Tu: ")

        if msg.lower() in ["salir", "exit", "quit"]:
            print("👋 ¡Hasta luego! Que disfrutes cocinar.")
            break

        try:
            # Generar receta con IA
            print("\n🔄 Generando receta...")
            receta, productos = generar_receta(nombreDef, msg, fromNumber, return_productos=True)

            print("\n=== 🍳 Respuesta del Chef ===\n")
            print(receta)
            print("\n" + "=" * 50 + "\n")

            # Preguntar si quiere hacer pedido
            hacer_pedido = input("🤖 ¿Querés hacer el pedido en un supermercado? (s/n): ").strip().lower()

            if hacer_pedido in ["s", "si", "sí", "y", "yes"]:
                # Filtramos supermercados disponibles
                supermercados = sorted(set([p.get("supermercado", "Desconocido") for p in productos]))
                if not supermercados:
                    print("⚠️ No hay supermercados disponibles para esta receta.")
                    continue

                print("\n🏪 Supermercados disponibles:")
                for i, sm in enumerate(supermercados, 1):
                    print(f"{i}. {sm}")
                print("0. Cancelar pedido")

                opcion = input("\n👉 Elegí una opción: ").strip()
                if opcion == "0":
                    print("👌 Pedido cancelado.")
                    continue

                try:
                    supermercado = supermercados[int(opcion) - 1]
                except Exception:
                    print("⚠️ Opción inválida. Pedido cancelado.")
                    continue

                # Filtrar productos por supermercado elegido
                productos_pedido = [p for p in productos if p.get("supermercado") == supermercado]

                if productos_pedido:
                    mostrar_resumen_pedido(productos_pedido)

                    if confirmar_pedido():
                        print(f"\n📤 Enviando pedido a {supermercado}...")
                        if enviar_pedido(supermercado, productos_pedido, fromNumber):
                            print("🎉 ¡Pedido enviado exitosamente!")
                        else:
                            print("❌ Error al enviar el pedido.")
                    else:
                        print("👌 Pedido cancelado.")
                else:
                    print(f"⚠️ No se encontraron productos en {supermercado}")
            else:
                print("👌 Perfecto. ¡Que disfrutes cocinando!")

        except Exception as e:
            print(f"\n❌ Error inesperado: {e}")
            print("💡 Intentá de nuevo o escribí 'salir' para terminar.")

if __name__ == "__main__":
    try:
        chatLocal()
    except KeyboardInterrupt:
        print("\n\n👋 Sesión terminada.")
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        print("💡 Verificá que todos los servicios estén corriendo.")
