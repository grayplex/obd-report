import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
from datetime import datetime

from app.api_client import api_client

st.set_page_config(page_title="Dashboard - OBD2", page_icon="📊", layout="wide")

st.title("Trip Dashboard")

# Fetch available trips
try:
    trips = api_client.list_trips()
except Exception as e:
    st.error(f"Error fetching trips: {str(e)}")
    trips = []

if not trips:
    st.info("No trips found. Upload a CSV file to get started.")
    st.stop()

# Trip selector
trip_options = {t["id"]: t["name"] for t in trips}

# Check for pre-selected trip from session state or query params
default_trip_id = st.session_state.get("selected_trip_id", trips[0]["id"])

selected_trip_id = st.selectbox(
    "Select Trip",
    options=list(trip_options.keys()),
    format_func=lambda x: trip_options[x],
    index=list(trip_options.keys()).index(default_trip_id) if default_trip_id in trip_options else 0,
)

# Fetch trip details and telemetry
try:
    trip = api_client.get_trip(selected_trip_id)
    telemetry = api_client.get_telemetry(selected_trip_id, limit=50000)
    gps_data = api_client.get_gps_points(selected_trip_id, downsample=1)
except Exception as e:
    st.error(f"Error fetching data: {str(e)}")
    st.stop()

# Trip statistics
st.subheader("Trip Statistics")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Duration", f"{trip['duration_seconds'] / 60:.1f} min")

with col2:
    max_speed = trip.get("max_speed_mph")
    st.metric("Max Speed", f"{max_speed:.1f} mph" if max_speed else "N/A")

with col3:
    avg_speed = trip.get("avg_speed_mph")
    st.metric("Avg Speed", f"{avg_speed:.1f} mph" if avg_speed else "N/A")

with col4:
    st.metric("Data Points", f"{trip.get('row_count', 0):,}")

with col5:
    start = datetime.fromisoformat(trip["start_time"].replace("Z", "+00:00"))
    st.metric("Date", start.strftime("%Y-%m-%d"))

# Convert telemetry to DataFrame
df = pd.DataFrame(telemetry["data"])
if df.empty:
    st.warning("No telemetry data available for this trip.")
    st.stop()

# Expand sensors column
if "sensors" in df.columns:
    sensors_df = pd.json_normalize(df["sensors"])
    df = pd.concat([df.drop("sensors", axis=1), sensors_df], axis=1)

# Charts section
st.subheader("Speed Over Time")

fig_speed = px.line(
    df,
    x="elapsed_seconds",
    y="speed_mph",
    labels={"elapsed_seconds": "Time (seconds)", "speed_mph": "Speed (MPH)"},
)
fig_speed.update_layout(height=400)
st.plotly_chart(fig_speed, use_container_width=True)

# Throttle chart
st.subheader("Throttle Positions")

throttle_cols = [col for col in df.columns if "throttle" in col.lower() or "pedal" in col.lower() or "accelerator" in col.lower()]

if throttle_cols:
    fig_throttle = go.Figure()
    for col in throttle_cols[:5]:  # Limit to 5 columns
        fig_throttle.add_trace(go.Scatter(
            x=df["elapsed_seconds"],
            y=df[col],
            name=col.replace("_", " ").title(),
            mode="lines",
        ))
    fig_throttle.update_layout(
        height=400,
        xaxis_title="Time (seconds)",
        yaxis_title="Position (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_throttle, use_container_width=True)
else:
    st.info("No throttle data available.")

# Cruise control chart
st.subheader("Cruise Control")

cruise_cols = [col for col in df.columns if "cruise" in col.lower()]

if cruise_cols:
    fig_cruise = go.Figure()
    for col in cruise_cols:
        fig_cruise.add_trace(go.Scatter(
            x=df["elapsed_seconds"],
            y=df[col],
            name=col.replace("_", " ").title(),
            mode="lines",
        ))
    fig_cruise.update_layout(
        height=300,
        xaxis_title="Time (seconds)",
        yaxis_title="Value",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_cruise, use_container_width=True)
else:
    st.info("No cruise control data available.")

# GPS Map
st.subheader("Route Map")

gps_points = gps_data.get("points", [])

if gps_points:
    # Calculate center
    lats = [p["lat"] for p in gps_points]
    lngs = [p["lng"] for p in gps_points]
    center_lat = sum(lats) / len(lats)
    center_lng = sum(lngs) / len(lngs)

    # Create map
    m = folium.Map(location=[center_lat, center_lng], zoom_start=13)

    # Add route line
    route_coords = [[p["lat"], p["lng"]] for p in gps_points]
    folium.PolyLine(route_coords, weight=3, color="blue", opacity=0.8).add_to(m)

    # Add start marker
    folium.Marker(
        [gps_points[0]["lat"], gps_points[0]["lng"]],
        popup="Start",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    # Add end marker
    folium.Marker(
        [gps_points[-1]["lat"], gps_points[-1]["lng"]],
        popup="End",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(m)

    st_folium(m, width=None, height=500, use_container_width=True)
else:
    st.info("No GPS data available for this trip.")

# Raw data section
with st.expander("View Raw Data"):
    st.dataframe(df, height=400)
