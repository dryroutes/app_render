from flask import Flask, request, jsonify, render_template
from grafo_loader import cargar_grafo_desde_jsons
import networkx as nx

app = Flask(__name__)
grafo = cargar_grafo_desde_jsons()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ruta", methods=["POST"])
def ruta():
    data = request.json
    origen = int(data["origen"])
    destino = int(data["destino"])

    try:
        camino = nx.shortest_path(grafo, origen, destino, weight="distancia")
        coords = [(grafo.nodes[n]["x"], grafo.nodes[n]["y"]) for n in camino]
        return jsonify({"ruta": coords})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
