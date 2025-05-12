import streamlit as st
import requests
import networkx as nx
import json
import os
import folium
from streamlit_folium import st_folium
from math import radians, cos, sin, sqrt, atan2
from google.colab import files

st.set_page_config(layout="wide")
st.title("🚶‍♂️ Safe Routes in Valencia")

st.markdown("""
<div style="background-color:#f0f0f5; padding:10px; border-radius:8px; margin-bottom:20px; color:#222;">
    <strong>📅 Weather Forecast for May 9, 2025 (Valencia):</strong><br>
    ⛈️ <em>Severe storms expected throughout the day</em><br>
    🌡️ Average temperature: <strong>18 °C</strong><br>
    💨 Strong wind from the east: <strong>40 km/h</strong><br>
    🌧️ Rain probability: <strong>95%</strong>
</div>
""", unsafe_allow_html=True)

criterion = st.selectbox(
    "🔎 What optimization criterion do you want to use for your safe route?",
    options={
        "distancia": "Shortest route (distance)",
        "tiempo": "Fastest route (time)",
        "altura": "Least exposed to flood height",
        "costo_total": "Lowest estimated risk"
    },
    format_func=lambda x: {
        "distancia": "Shortest route (distance)",
        "tiempo": "Fastest route (time)",
        "altura": "Least exposed to flood height",
        "costo_total": "Lowest estimated risk"
    }[x]
)

# Initialize session state
for key in ["graph", "origin_coords", "destination_coords", "node1", "node2", "error", "nodes", "parkings"]:
    if key not in st.session_state:
        st.session_state[key] = None

@st.cache_data
def load_nodes():
    nodes = []
    for file in os.listdir("graph/nodes"):
        if file.endswith(".json"):
            with open(f"graph/nodes/{file}") as f:
                nodes.extend(json.load(f))
    return nodes

def distance_coords(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def closest_node(lat, lon, nodes):
    return min(nodes, key=lambda n: distance_coords(lat, lon, n["y"], n["x"]))["id"]

def reverse_geocode(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=17&addressdetails=0"
        headers = {"User-Agent": "safe-routes-app"}
        r = requests.get(url, headers=headers, timeout=4)
        return r.json().get("display_name", "Unknown location")
    except:
        return "Unknown location"

def search_addresses(query):
    try:
        url = f"https://photon.komoot.io/api/?q={query}, Valencia, Spain&limit=5"
        r = requests.get(url, timeout=4)
        results = r.json()["features"]
        return [(res["properties"].get("name", "") + ", " + res["properties"].get("city", ""),
                 res["geometry"]["coordinates"][1], res["geometry"]["coordinates"][0]) for res in results]
    except:
        return []

def load_resources():
    with open("emergency_services_valencia.json") as f1, \
         open("incidents_valencia_2025-05-09.json") as f2, \
         open("parkings_valencia_binary.json") as f3:
        emergency = json.load(f1)
        incidents = json.load(f2)
        parkings = json.load(f3)
    return emergency, incidents, parkings

def penalize_risk(G, emergency, incidents):
    for u, v, data in G.edges(data=True):
        if data.get("height", 0) > 0:
            y, x = G.nodes[u]["y"], G.nodes[u]["x"]
            for r in emergency + incidents:
                ry = r.get("latitud", r.get("lat"))
                rx = r.get("longitud", r.get("lng"))
                if distance_coords(y, x, ry, rx) < 150:
                    for k in ["distancia", "tiempo", "costo_total", "altura"]:
                        if k in data:
                            data[k] *= 2
                    break

def nearest_parking(y_dest, x_dest, parkings):
    return min(parkings, key=lambda p: distance_coords(y_dest, x_dest, p["lat"], p["lon"]))

def load_subgraph(node1, node2):
    desired_nodes = set()
    all_nodes = st.session_state.nodes
    id_coords = {n["id"]: (n["y"], n["x"]) for n in all_nodes}

    lat1, lon1 = id_coords[node1]
    lat2, lon2 = id_coords[node2]
    d = distance_coords(lat1, lon1, lat2, lon2)
    radius = int(d / 2 + 800)
    st.info(f"🔄 Loading subgraph with radius ~{radius} m...")

    for n in all_nodes:
        lat, lon = n["y"], n["x"]
        if (distance_coords(lat1, lon1, lat, lon) < radius or
            distance_coords(lat2, lon2, lat, lon) < radius):
            desired_nodes.add(n["id"])

    G = nx.DiGraph()
    for n_id in desired_nodes:
        lat, lon = id_coords[n_id]
        G.add_node(n_id, y=lat, x=lon)

    for file in os.listdir("graph/edges"):
        if file.endswith(".json"):
            with open(f"graph/edges/{file}") as f:
                for e in json.load(f):
                    if e["origen"] in desired_nodes and e["destino"] in desired_nodes:
                        G.add_edge(
                            e["origen"], e["destino"],
                            distancia=e["distancia"],
                            tiempo=e["tiempo"],
                            costo_total=e["costo_total"],
                            altura=e["altura_media"]
                        )
    return G, id_coords

if st.session_state.nodes is None:
    st.session_state.nodes = load_nodes()

col1, col2 = st.columns([1, 2])

with col1:
    query1 = st.text_input("📍 Origin address")
    opt1 = search_addresses(query1) if query1 else []
    sel1 = st.selectbox("Select origin", opt1, format_func=lambda x: x[0]) if opt1 else None

    query2 = st.text_input("🎯 Destination address")
    opt2 = search_addresses(query2) if query2 else []
    sel2 = st.selectbox("Select destination", opt2, format_func=lambda x: x[0]) if opt2 else None

    if st.button("Calculate route"):
        if not sel1 or not sel2:
            st.warning("Please select both origin and destination.")
            st.stop()
        try:
            lat1, lon1 = sel1[1], sel1[2]
            lat2, lon2 = sel2[1], sel2[2]
            node1 = closest_node(lat1, lon1, st.session_state.nodes)
            node2 = closest_node(lat2, lon2, st.session_state.nodes)
            G, id_coords = load_subgraph(node1, node2)

            emergency, incidents, parkings = load_resources()
            penalize_risk(G, emergency, incidents)

            st.session_state.graph = G
            st.session_state.origin_coords = (G.nodes[node1]["y"], G.nodes[node1]["x"])
            st.session_state.destination_coords = (G.nodes[node2]["y"], G.nodes[node2]["x"])
            st.session_state.node1 = node1
            st.session_state.node2 = node2
            st.session_state.parkings = parkings
            st.session_state.error = None

        except Exception as e:
            st.session_state.graph = None
            st.session_state.error = str(e)

if st.session_state.graph and st.session_state.origin_coords and st.session_state.destination_coords:
    G = st.session_state.graph
    y1, x1 = st.session_state.origin_coords
    y2, x2 = st.session_state.destination_coords
    node1 = st.session_state.node1
    node2 = st.session_state.node2

    m = folium.Map(location=[(y1 + y2)/2, (x1 + x2)/2], zoom_start=14)

    folium.Marker([y1, x1], tooltip=reverse_geocode(y1, x1), icon=folium.Icon(color="green")).add_to(m)
    folium.Marker([y2, x2], tooltip=reverse_geocode(y2, x2), icon=folium.Icon(color="red")).add_to(m)

    try:
        route = None
        mode = "directed"

        if nx.has_path(G, node1, node2):
            route = nx.shortest_path(G, node1, node2, weight=criterion)
        elif nx.has_path(G.to_undirected(), node1, node2):
            route = nx.shortest_path(G.to_undirected(), node1, node2, weight=criterion)
            mode = "undirected"

        if route:
            coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route]
            folium.PolyLine(coords, color="blue", weight=4).add_to(m)

            total_distance = sum(G[u][v].get("distancia", 0) for u, v in zip(route[:-1], route[1:]))
            total_time = sum(G[u][v].get("tiempo", 0) for u, v in zip(route[:-1], route[1:])) * 60
            risky_edges = sum(1 for u, v in zip(route[:-1], route[1:]) if G[u][v].get("altura", 0) > 0)
            risky_nodes = sum(1 for n in route if G.nodes[n].get("altura", 0) > 0)

            with col1:
                st.success(f"Route found ({len(route)} nodes, {mode} mode)")
                st.markdown(f"🧶 Optimized criterion: **{criterion}**")
                st.markdown(f"📏 Total distance: **{total_distance:.1f} m**")
                st.markdown(f"⏱️ Estimated time: **{total_time:.0f} seconds**")
                st.markdown(f"⚠️ Risky edges: **{risky_edges}**")
                st.markdown(f"⚠️ Risky nodes: **{risky_nodes}**")

                if mode == "undirected":
                    st.warning("⚠️ Undirected mode used. The route may not follow real street directions.")

                p = nearest_parking(y2, x2, st.session_state.parkings)
                p_address = reverse_geocode(p["lat"], p["lon"])
                folium.Marker([p["lat"], p["lon"]], tooltip=p_address, icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

                if p["is_underground"] == 1:
                    if any(G[u][v].get("altura", 0) > 0 for u, v in zip(route[:-1], route[1:])):
                        st.warning(f"🚨 The nearest parking is underground and flooding risk exists. ({p_address})")
                    else:
                        st.info(f"ℹ️ The nearest parking is underground. ({p_address})")
                else:
                    st.success(f"🄹 The nearest parking is above ground. ({p_address})")

    except Exception as e:
        with col1:
            st.error(f"Error calculating route: {e}")

    with col2:
        st_folium(m, use_container_width=True, height=600)

elif st.session_state.error:
    st.error(st.session_state.error)
