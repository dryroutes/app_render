from flask import Flask, request, jsonify, render_template
from grafo_loader import cargar_grafo_desde_jsons
import networkx as nx

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ruta", methods=["POST"])
def ruta():
    data = request.json
    origen = int(data["origen"])
    destino = int(data["destino"])

    try:
        grafo = cargar_grafo_desde_jsons()  # se carga SOLO cuando se pide
        camino = nx.shortest_path(grafo, origen, destino, weight="distancia")
        coords = [(grafo.nodes[n]["x"], grafo.nodes[n]["y"]) for n in camino]
        return jsonify({"ruta": coords})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/nodo_mas_cercano", methods=["POST"])
def nodo_mas_cercano():
    data = request.json
    x_click = data["x"]
    y_click = data["y"]

    # Buscar nodo más cercano por distancia euclídea
    grafo = cargar_grafo_desde_jsons()  # carga on-demand

    min_dist = float("inf")
    nodo_mas_cercano = None
    for nodo, attrs in grafo.nodes(data=True):
        dx = x_click - attrs["x"]
        dy = y_click - attrs["y"]
        dist = dx**2 + dy**2
        if dist < min_dist:
            min_dist = dist
            nodo_mas_cercano = nodo

    return jsonify({"nodo": nodo_mas_cercano})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
