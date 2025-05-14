import streamlit as st
import networkx as nx
import json
import os
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2
import gzip
from PIL import Image
import io

st.set_page_config(layout="wide")
st.title("🚶‍♂️ Safe Routes in L'Horta Sud")

st.markdown("""
<div style="background-color:#f0f0f5; padding:10px; border-radius:8px; margin-bottom:20px; color:#222;">
    <strong>🗕️ Weather forecast :</strong><br>
    ⛈️ <em>Severe storm with torrential rain and localized flooding</em><br>
    🌡️ Average temperature: <strong>19 °C</strong><br>
    🌬️ Strong easterly winds: <strong>45 km/h</strong><br>
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

for key in ["grafo", "origen_coords", "destino_coords", "nodo1", "nodo2", "error", "nodos", "parkings", "incidencias", "emergencia", "ruta"]:
    if key not in st.session_state:
        st.session_state[key] = None

@st.cache_data
def cargar_nodos():
    nodos = []
    carpeta = "grafo/nodos"
    if not os.path.exists(carpeta):
        return nodos
    for archivo in os.listdir(carpeta):
        if archivo.endswith(".json.gz"):
            with gzip.open(os.path.join(carpeta, archivo), "rt", encoding="utf-8") as f:
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
    if not nodos:
        raise ValueError("No nodes available to find the nearest node.")
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
    puntos = []
    for inc in incidencias:
        if "lat" in inc and "lng" in inc:
            puntos.append((inc["lat"], inc["lng"]))
    for s in emergencia:
        lat = s.get("latitud", s.get("lat"))
        lon = s.get("longitud", s.get("lng"))
        if lat and lon:
            puntos.append((lat, lon))
    for u, v, data in G.edges(data=True):
        if data.get("altura", 0) > 0:
            y, x = G.nodes[u]["y"], G.nodes[u]["x"]
            for ry, rx in puntos:
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
    sel2 = st.selectbox("🌟 Select destination", destinos, index=1, format_func=lambda x: x[0])

    if st.button("Calculate route"):
        try:
            lat1, lon1 = sel1[1], sel1[2]
            lat2, lon2 = sel2[1], sel2[2]
            nodo1 = nodo_mas_cercano(lat1, lon1, st.session_state.nodos)
            nodo2 = nodo_mas_cercano(lat2, lon2, st.session_state.nodos)
            G, id_coords = cargar_subgrafo(nodo1, nodo2)
            emergencia, incidencias, parkings = cargar_recursos()
            penalizar_riesgo(G, emergencia, incidencias)

            st.session_state.update({
                "grafo": G,
                "origen_coords": (G.nodes[nodo1]["y"], G.nodes[nodo1]["x"]),
                "destino_coords": (G.nodes[nodo2]["y"], G.nodes[nodo2]["x"]),
                "nodo1": nodo1,
                "nodo2": nodo2,
                "parkings": parkings,
                "incidencias": incidencias,
                "emergencia": emergencia,
                "ruta": [],
                "error": None
            })
        except Exception as e:
            st.session_state.error = str(e)

if st.session_state.grafo:
    G = st.session_state.grafo
    y1, x1 = st.session_state.origen_coords
    y2, x2 = st.session_state.destino_coords
    nodo1 = st.session_state.nodo1
    nodo2 = st.session_state.nodo2
    incidencias = st.session_state.incidencias
    emergencia = st.session_state.emergencia

    m = folium.Map(location=[(y1 + y2)/2, (x1 + x2)/2], zoom_start=14)
    folium.Marker([y1, x1], tooltip=reverse_geocode(y1, x1), icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([y2, x2], tooltip=reverse_geocode(y2, x2), icon=folium.Icon(color="red")).add_to(m)

    try:
        pesos_validos = all(criterio in data for _, _, data in G.edges(data=True))
        if nx.has_path(G, nodo1, nodo2):
            ruta = nx.shortest_path(G, nodo1, nodo2, weight=criterio if pesos_validos else None)
        else:
            ruta = nx.shortest_path(G.to_undirected(), nodo1, nodo2, weight=criterio if pesos_validos else None)

        st.session_state["ruta"] = ruta

        for u, v in zip(ruta[:-1], ruta[1:]):
            try:
                if G.has_edge(u, v): edge = G[u][v]
                elif G.has_edge(v, u): edge = G[v][u]
                else: continue
                y_u, x_u = G.nodes[u].get("y"), G.nodes[u].get("x")
                y_v, x_v = G.nodes[v].get("y"), G.nodes[v].get("x")
                if y_u is None or x_u is None or y_v is None or x_v is None:
                    continue
                color = "red" if edge.get("altura", 0) > 0 else "blue"
                coords = [(y_u, x_u), (y_v, x_v)]
                folium.PolyLine(coords, color=color, weight=5).add_to(m)
            except:
                continue

        for inc in incidencias:
            if "lat" in inc and "lng" in inc:
                for n in ruta:
                    y, x = G.nodes[n]["y"], G.nodes[n]["x"]
                    if distancia_coords(y, x, inc["lat"], inc["lng"]) < 150:
                        folium.CircleMarker([inc["lat"], inc["lng"]], radius=6, color="orange", fill=True, fill_opacity=0.7, tooltip="Incidencia").add_to(m)
                        break

        for s in emergencia:
            lat = s.get("latitud", s.get("lat"))
            lon = s.get("longitud", s.get("lng"))
            if lat and lon:
                for n in ruta:
                    y, x = G.nodes[n]["y"], G.nodes[n]["x"]
                    if distancia_coords(y, x, lat, lon) < 150:
                        folium.CircleMarker([lat, lon], radius=6, color="purple", fill=True, fill_opacity=0.7, tooltip=s.get("nombre", "Servicio emergencia")).add_to(m)
                        break

        st.success("Route calculated correctly.")
        with col2:
            st_folium(m, width=700, height=500, key="map_rendered")

            with st.expander("🧾 Route details and download"):
                    try:
                        distancia_total = sum(G[u][v].get("distancia", 0) for u, v in zip(ruta[:-1], ruta[1:]) if G.has_edge(u, v))
                        tiempo_total = sum(G[u][v].get("tiempo", 0) for u, v in zip(ruta[:-1], ruta[1:]) if G.has_edge(u, v))
                        riesgo = sum(1 for u, v in zip(ruta[:-1], ruta[1:]) if G.has_edge(u, v) and G[u][v].get("altura", 0) > 0)
        
                        st.write(f"📏 Total distance: {distancia_total:.1f} m")
                        st.write(f"⏱️ Estimated time: {tiempo_total:.0f} seconds")
                        st.write(f"⚠️ Risky segments: {riesgo}")
        
                        # Guardar mapa como HTML para descarga
                        map_html_path = "map_output.html"
                        m.save(map_html_path)
                        with open(map_html_path, "rb") as f:
                            st.download_button(
                                label="📥 Download map as HTML",
                                data=f.read(),
                                file_name="safe_route_map.html",
                                mime="text/html"
                            )
                    except Exception as e:
                        st.error(f"Error generating route summary or download button: {e}")
        except: 
            continue
        # Nota: para generar imagen, deberías usar selenium o folium-screenshot desde fuera de Streamlit


