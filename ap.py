import streamlit as st
import requests
import networkx as nx
import json
import os
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2

st.set_page_config(layout="wide")
st.title("🚶‍♂️ Safe Routes in Valencia")

st.markdown("""
<div style="background-color:#f0f0f5; padding:10px; border-radius:8px; margin-bottom:20px; color:#222;">
    <strong>📅 Weather forecast :</strong><br>
    ⛈️ <em>Severe storm with torrential rain and localized flooding</em><br>
    🌡️ Average temperature: <strong>19 °C</strong><br>
    💨 Strong easterly winds: <strong>45 km/h</strong><br>
    🌧️ Rain probability: <strong>100%</strong><br>
    ⚠️ <strong>Red alert for potential flash floods</strong>
</div>
""", unsafe_allow_html=True)

criterio = st.selectbox(
    "🔎 What criterion do you want to optimize for the safest route?",
    options={
        "distancia": "Shortest route (distance)",
        "tiempo": "Fastest route (time)",
        "altura": "Route with lowest flood level (water height)",
        "costo_total": "Route with lowest estimated risk"
    },
    format_func=lambda x: {
        "distancia": "Shortest route (distance)",
        "tiempo": "Fastest route (time)",
        "altura": "Route with lowest flood level (water height)",
        "costo_total": "Route with lowest estimated risk"
    }[x]
)

for key in ["grafo", "origen_coords", "destino_coords", "nodo1", "nodo2", "error", "nodos", "parkings"]:
    if key not in st.session_state:
        st.session_state[key] = None

@st.cache_data
def cargar_nodos():
    nodos = []
    for archivo in os.listdir("grafo/nodos"):
        if archivo.endswith(".json"):
            with open(f"grafo/nodos/{archivo}") as f:
                nodos.extend(json.load(f))
    return nodos

def distancia_coords(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def nodo_mas_cercano(lat, lon, nodos):
    return min(nodos, key=lambda n: distancia_coords(lat, lon, n["y"], n["x"]))["id"]

def reverse_geocode(lat, lon):
    return f"{lat:.5f}, {lon:.5f}"

def cargar_recursos():
    with open("servicios_emergencia_provincia_valencia.json") as f1, \
         open("incidencias_valencia_2025-05-09.json") as f2, \
         open("parkings_valencia_binario.json") as f3:
        emergencia = json.load(f1)
        incidencias = json.load(f2)
        parkings = json.load(f3)
    return emergencia, incidencias, parkings

def penalizar_riesgo(G, emergencia, incidencias):
    for u, v, data in G.edges(data=True):
        if data.get("altura", 0) > 0:
            y, x = G.nodes[u]["y"], G.nodes[u]["x"]
            for recurso in emergencia + incidencias:
                ry = recurso.get("latitud", recurso.get("lat"))
                rx = recurso.get("longitud", recurso.get("lng"))
                if distancia_coords(y, x, ry, rx) < 150:
                    for k in ["distancia", "tiempo", "costo_total", "altura"]:
                        if k in data:
                            data[k] *= 2
                    break

def parking_cercano(y_dest, x_dest, parkings):
    return min(parkings, key=lambda p: distancia_coords(y_dest, x_dest, p["lat"], p["lon"]))

def cargar_subgrafo(nodo1, nodo2):
    nodos_deseados = set()
    todos_nodos = st.session_state.nodos
    id_coords = {n["id"]: (n["y"], n["x"]) for n in todos_nodos}

    lat1, lon1 = id_coords[nodo1]
    lat2, lon2 = id_coords[nodo2]
    d = distancia_coords(lat1, lon1, lat2, lon2)
    radio = int(d / 2 + 800)
    st.info(f"🔄 Loading subgraph with ~{radio} m radius to connect origin and destination...")

    for n in todos_nodos:
        lat, lon = n["y"], n["x"]
        if (distancia_coords(lat1, lon1, lat, lon) < radio or distancia_coords(lat2, lon2, lat, lon) < radio):
            nodos_deseados.add(n["id"])

    G = nx.DiGraph()
    for n_id in nodos_deseados:
        lat, lon = id_coords[n_id]
        G.add_node(n_id, y=lat, x=lon)
        import gzip

    for archivo in os.listdir("grafo/aristas"):
        if archivo.endswith(".json.gz"):
            with gzip.open(f"grafo/aristas/{archivo}", "rt", encoding="utf-8") as f:
                for a in json.load(f):
                    if a["origen"] in nodos_deseados and a["destino"] in nodos_deseados:
                        G.add_edge(
                            a["origen"], a["destino"],
                            distancia=a.get("distancia", 1),
                            tiempo=a.get("tiempo", 1),
                            costo_total=a.get("costo_total", 1),
                            altura=a.get("altura_media", 0)
                        )

    return G, id_coords

if st.session_state.nodos is None:
    st.session_state.nodos = cargar_nodos()

col1, col2 = st.columns([1, 2])

with col1:
    origenes = [
        ("Av. País Valencià, Paiporta", 39.42966, -0.41488),
        ("Calle Picanya, Valencia", 39.46400, -0.40312),
        ("Calle Mayor, Sedaví", 39.42585, -0.38217),
        ("Calle San Vicente, Aldaia", 39.46610, -0.46050),
        ("Av. del Cid, Valencia", 39.47153, -0.40540)
    ]

    destinos = [
        ("Calle Ausiàs March, Catarroja", 39.40470, -0.41512),
        ("Av. Blasco Ibáñez, Torrent", 39.43794, -0.46526),
        ("Plaza del Ayuntamiento, Valencia", 39.46994, -0.37629),
        ("Av. Albufera, Alfafar", 39.42481, -0.38191),
        ("Calle Valencia, Benetússer", 39.42861, -0.39243)
    ]

    sel1 = st.selectbox("📍 Select origin", origenes, index=0, format_func=lambda x: x[0])
    sel2 = st.selectbox("🎯 Select destination", destinos, index=1, format_func=lambda x: x[0])

    if st.button("Calculate route"):
        try:
            lat1, lon1 = sel1[1], sel1[2]
            lat2, lon2 = sel2[1], sel2[2]
            nodo1 = nodo_mas_cercano(lat1, lon1, st.session_state.nodos)
            nodo2 = nodo_mas_cercano(lat2, lon2, st.session_state.nodos)
            G, id_coords = cargar_subgrafo(nodo1, nodo2)
            # 👇 Diagnóstico inmediato
            num_nodos = G.number_of_nodes()
            num_aristas = G.number_of_edges()
            ejemplo_arista = next(iter(G.edges(data=True)), None)
            
            st.warning(f"🧠 Subgraph loaded: {num_nodos} nodes, {num_aristas} edges.")
            if ejemplo_arista:
                st.info(f"Example edge data: {ejemplo_arista[2]}")
            else:
                st.error("⚠️ No edges found in the subgraph.")


            emergencia, incidencias, parkings = cargar_recursos()
            penalizar_riesgo(G, emergencia, incidencias)

            st.session_state.grafo = G
            st.session_state.origen_coords = (G.nodes[nodo1]["y"], G.nodes[nodo1]["x"])
            st.session_state.destino_coords = (G.nodes[nodo2]["y"], G.nodes[nodo2]["x"])
            st.session_state.nodo1 = nodo1
            st.session_state.nodo2 = nodo2
            st.session_state.parkings = parkings
            st.session_state.error = None

        except Exception as e:
            st.session_state.grafo = None
            st.session_state.error = str(e)

if st.session_state.grafo and st.session_state.origen_coords and st.session_state.destino_coords:
    G = st.session_state.grafo
    y1, x1 = st.session_state.origen_coords
    y2, x2 = st.session_state.destino_coords
    nodo1 = st.session_state.nodo1
    nodo2 = st.session_state.nodo2

    m = folium.Map(location=[(y1 + y2)/2, (x1 + x2)/2], zoom_start=14)

    folium.Marker([y1, x1], tooltip=reverse_geocode(y1, x1), icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([y2, x2], tooltip=reverse_geocode(y2, x2), icon=folium.Icon(color="red")).add_to(m)

    try:
        ruta = None
        modo = ""
        pesos_validos = all(criterio in data for _, _, data in G.edges(data=True))

        if nx.has_path(G, nodo1, nodo2):
            if pesos_validos:
                ruta = nx.shortest_path(G, nodo1, nodo2, weight=criterio)
                modo = "directed with weight"
            else:
                ruta = nx.shortest_path(G, nodo1, nodo2)
                modo = "directed unweighted"
        elif nx.has_path(G.to_undirected(), nodo1, nodo2):
            if pesos_validos:
                ruta = nx.shortest_path(G.to_undirected(), nodo1, nodo2, weight=criterio)
                modo = "undirected with weight"
            else:
                ruta = nx.shortest_path(G.to_undirected(), nodo1, nodo2)
                modo = "undirected unweighted"

        if ruta:
            coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in ruta]
            folium.PolyLine(coords, color="blue", weight=4).add_to(m)
            distancia_total = 0
            tiempo_total = 0
            aristas_riesgo = 0
            
            for u, v in zip(ruta[:-1], ruta[1:]):
                if G.has_edge(u, v):
                    edge = G[u][v]
                elif G.has_edge(v, u):  # fallback en caso de grafo no dirigido
                    edge = G[v][u]
                else:
                    continue  # arista no encontrada
            
                distancia_total += edge.get("distancia", 0)
                tiempo_total += edge.get("tiempo", 0)
                if edge.get("altura", 0) > 0:
                    aristas_riesgo += 1
            nodos_riesgo = sum(1 for n in ruta if G.nodes[n].get("altura", 0) > 0)

            with col1:
                st.success(f"Route found ({len(ruta)} nodes, {modo})")
                st.markdown(f"🧶 Optimized criterion: **{criterio}**")
                st.markdown(f"📏 Total distance: **{distancia_total:.1f} m**")
                st.markdown(f"⏱️ Estimated time: **{tiempo_total:.0f} seconds**")
                st.markdown(f"⚠️ Risky segments: **{aristas_riesgo}**")
                st.markdown(f"⚠️ Risky nodes: **{nodos_riesgo}**")

                if "unweighted" in modo:
                    st.warning("⚠️ The selected criterion was missing in some edges. Used fallback path without weights.")

                p = parking_cercano(y2, x2, st.session_state.parkings)
                direccion_p = reverse_geocode(p["lat"], p["lon"])
                folium.Marker([p["lat"], p["lon"]], tooltip=direccion_p, icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

                if p["is_underground"] == 1 and aristas_riesgo > 0:
                    st.warning(f"🚨 The nearest parking is underground and there is flood risk. ({direccion_p})")
                elif p["is_underground"] == 1:
                    st.info(f"ℹ️ The nearest parking is underground. ({direccion_p})")
                else:
                    st.success(f"🄹 The nearest parking is at street level. ({direccion_p})")

    except Exception as e:
        with col1:
            st.error(f"Error calculating route: {e}")

    with col2:
        st_folium(m, use_container_width=True, height=600)

elif st.session_state.error:
    st.error(st.session_state.error)
