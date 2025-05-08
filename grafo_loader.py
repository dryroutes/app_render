import json
import os
import networkx as nx

def cargar_grafo_desde_jsons(carpeta_nodos="grafo/nodos", carpeta_aristas="grafo/aristas"):
    G = nx.DiGraph()  # Usamos dirigido por si importa el sentido

    # Cargar nodos
    for archivo in os.listdir(carpeta_nodos):
        if archivo.endswith(".json"):
            with open(os.path.join(carpeta_nodos, archivo)) as f:
                nodos = json.load(f)
                for nodo in nodos:
                    G.add_node(nodo["id"], x=nodo["x"], y=nodo["y"])

    # Cargar aristas
    for archivo in os.listdir(carpeta_aristas):
        if archivo.endswith(".json"):
            with open(os.path.join(carpeta_aristas, archivo)) as f:
                aristas = json.load(f)
                for arista in aristas:
                    G.add_edge(
                        arista["origen"],
                        arista["destino"],
                        distancia=arista["distancia"],
                        tiempo=arista["tiempo"],
                        costo=arista["costo_total"],
                        altura=arista["altura_media"]
                    )
    return G
