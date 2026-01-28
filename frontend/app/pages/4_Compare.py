import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from app.api_client import api_client

st.set_page_config(page_title="Compare - OBD2", page_icon="📈", layout="wide")

st.title("Trip Comparison")

# Fetch available trips
try:
    trips = api_client.list_trips()
except Exception as e:
    st.error(f"Error fetching trips: {str(e)}")
    trips = []

if len(trips) < 2:
    st.info("Upload at least 2 trips to use the comparison feature.")
    st.stop()

# Multi-select trips
trip_options = {t["id"]: t["name"] for t in trips}

selected_trip_ids = st.multiselect(
    "Select trips to compare (2-5 trips)",
    options=list(trip_options.keys()),
    format_func=lambda x: trip_options[x],
    max_selections=5,
)

if len(selected_trip_ids) < 2:
    st.info("Select at least 2 trips to compare.")
    st.stop()

# Fetch data for selected trips
trip_data = {}
telemetry_data = {}

for trip_id in selected_trip_ids:
    try:
        trip_data[trip_id] = api_client.get_trip(trip_id)
        telemetry_data[trip_id] = api_client.get_telemetry(trip_id, limit=50000)
    except Exception as e:
        st.error(f"Error fetching data for trip {trip_options[trip_id]}: {str(e)}")

# Comparison table
st.subheader("Trip Metrics Comparison")

comparison_data = []
for trip_id, trip in trip_data.items():
    start = datetime.fromisoformat(trip["start_time"].replace("Z", "+00:00"))
    comparison_data.append({
        "Trip": trip["name"],
        "Date": start.strftime("%Y-%m-%d"),
        "Duration (min)": f"{trip['duration_seconds'] / 60:.1f}",
        "Max Speed (mph)": f"{trip.get('max_speed_mph', 0):.1f}" if trip.get('max_speed_mph') else "N/A",
        "Avg Speed (mph)": f"{trip.get('avg_speed_mph', 0):.1f}" if trip.get('avg_speed_mph') else "N/A",
        "Data Points": f"{trip.get('row_count', 0):,}",
    })

comparison_df = pd.DataFrame(comparison_data)
st.dataframe(comparison_df, hide_index=True, use_container_width=True)

# Speed overlay chart
st.subheader("Speed Comparison")

fig_speed = go.Figure()

colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

for i, (trip_id, data) in enumerate(telemetry_data.items()):
    df = pd.DataFrame(data["data"])
    trip_name = trip_data[trip_id]["name"]
    color = colors[i % len(colors)]

    fig_speed.add_trace(go.Scatter(
        x=df["elapsed_seconds"],
        y=df["speed_mph"],
        name=trip_name,
        mode="lines",
        line=dict(color=color),
    ))

fig_speed.update_layout(
    height=500,
    xaxis_title="Time (seconds)",
    yaxis_title="Speed (MPH)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
)

st.plotly_chart(fig_speed, use_container_width=True)

# Statistics comparison
st.subheader("Statistics Summary")

col1, col2 = st.columns(2)

with col1:
    # Max speed bar chart
    max_speeds = [
        {"Trip": trip_data[tid]["name"], "Max Speed": trip_data[tid].get("max_speed_mph", 0) or 0}
        for tid in selected_trip_ids
    ]
    fig_max = go.Figure(data=[
        go.Bar(
            x=[d["Trip"] for d in max_speeds],
            y=[d["Max Speed"] for d in max_speeds],
            marker_color=colors[:len(max_speeds)],
        )
    ])
    fig_max.update_layout(
        title="Max Speed Comparison",
        yaxis_title="Speed (MPH)",
        height=350,
    )
    st.plotly_chart(fig_max, use_container_width=True)

with col2:
    # Average speed bar chart
    avg_speeds = [
        {"Trip": trip_data[tid]["name"], "Avg Speed": trip_data[tid].get("avg_speed_mph", 0) or 0}
        for tid in selected_trip_ids
    ]
    fig_avg = go.Figure(data=[
        go.Bar(
            x=[d["Trip"] for d in avg_speeds],
            y=[d["Avg Speed"] for d in avg_speeds],
            marker_color=colors[:len(avg_speeds)],
        )
    ])
    fig_avg.update_layout(
        title="Average Speed Comparison",
        yaxis_title="Speed (MPH)",
        height=350,
    )
    st.plotly_chart(fig_avg, use_container_width=True)

# Duration comparison
durations = [
    {"Trip": trip_data[tid]["name"], "Duration": trip_data[tid]["duration_seconds"] / 60}
    for tid in selected_trip_ids
]
fig_duration = go.Figure(data=[
    go.Bar(
        x=[d["Trip"] for d in durations],
        y=[d["Duration"] for d in durations],
        marker_color=colors[:len(durations)],
    )
])
fig_duration.update_layout(
    title="Trip Duration Comparison",
    yaxis_title="Duration (minutes)",
    height=350,
)
st.plotly_chart(fig_duration, use_container_width=True)
