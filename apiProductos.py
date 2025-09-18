from flask import Flask, jsonify, request
import pandas as pd
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Definir ruta relativa a la carpeta actual
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(BASE_DIR, "productos.xlsx")

# Leer Excel
df = pd.read_excel(file_path, sheet_name="Precios medianos por cadena")

# Convertir a formato largo
df_long = df.melt(
    id_vars=["grupo", "nombre_producto"],
    var_name="supermercado",
    value_name="precio"
).dropna()

productos = df_long.to_dict(orient="records")

# ======================
# Rutas API
# ======================
@app.route("/productos", methods=["GET"])
def get_all():
    return jsonify(productos), 200

@app.route("/productos/<super>", methods=["GET"])
def get_by_super(super):
    filtrados = [p for p in productos if str(p["supermercado"]).lower() == super.lower()]
    return jsonify(filtrados), 200

@app.route("/productos", methods=["POST"])
def add_producto():
    data = request.get_json()
    if not data or "nombre_producto" not in data or "precio" not in data or "supermercado" not in data:
        return jsonify({"error": "Faltan campos"}), 400
    productos.append(data)
    return jsonify({"mensaje": "Producto agregado", "producto": data}), 201

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5003, debug=True)
