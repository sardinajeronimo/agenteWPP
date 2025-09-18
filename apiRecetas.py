from flask import Flask, request, jsonify
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

# Lista en memoria para guardar los pedidos
pedidos = []


@app.route("/pedidos", methods=["POST"])
def crear_pedido():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No se recibió un pedido válido"}), 400

    pedidos.append(data)
    return jsonify({
        "mensaje": "Pedido creado con éxito",
        "pedido": data
    }), 201


@app.route("/pedidos", methods=["GET"])
def listar_pedidos():
    return jsonify(pedidos), 200


@app.route("/pedidos", methods=["DELETE"])
def borrar_pedidos():
    pedidos.clear()
    return jsonify({"mensaje": "Todos los pedidos fueron eliminados"}), 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
