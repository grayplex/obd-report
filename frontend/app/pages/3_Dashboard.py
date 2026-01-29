import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
from datetime import datetime
import numpy as np

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
default_trip_id = st.session_state.get("selected_trip_id", trips[0]["id"])

selected_trip_id = st.selectbox(
    "Select Trip",
    options=list(trip_options.keys()),
    format_func=lambda x: trip_options[x],
    index=list(trip_options.keys()).index(default_trip_id) if default_trip_id in trip_options else 0,
)

# Fetch trip details, telemetry, and analytics
try:
    trip = api_client.get_trip(selected_trip_id)
    summary = api_client.get_trip_summary(selected_trip_id)
    advanced = api_client.get_advanced_analytics(selected_trip_id)
    telemetry = api_client.get_telemetry(selected_trip_id, limit=50000)
    gps_data = api_client.get_gps_points(selected_trip_id, downsample=1)
    events_data = api_client.get_trip_events(selected_trip_id)
except Exception as e:
    st.error(f"Error fetching data: {str(e)}")
    st.stop()

# Extract analytics
trip_info = summary.get("trip", {})
distance_info = summary.get("distance", {})
time_breakdown = summary.get("time_breakdown", {})
fuel_economy = summary.get("fuel_economy", {})
driving_behavior = summary.get("driving_behavior", {})
speed_ranges = advanced.get("speed_ranges", {})
throttle_patterns = advanced.get("throttle_patterns", {})
cruise_stats = advanced.get("cruise_control", {})
fuel_insights = advanced.get("fuel_insights", {})

# ===== TRIP OVERVIEW =====
st.subheader("📍 Trip Overview")
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    duration_min = trip_info.get("duration_seconds", 0) / 60
    st.metric("Duration", f"{duration_min:.1f} min")

with col2:
    distance = distance_info.get("total_miles")
    if distance:
        st.metric("Distance", f"{distance:.2f} mi")
    else:
        st.metric("Distance", "N/A")

with col3:
    avg_speed = distance_info.get("avg_speed_mph")
    if avg_speed:
        st.metric("Avg Speed", f"{avg_speed:.1f} mph")
    else:
        st.metric("Avg Speed", "N/A")

with col4:
    max_speed = distance_info.get("max_speed_mph")
    if max_speed:
        st.metric("Max Speed", f"{max_speed:.1f} mph")
    else:
        st.metric("Max Speed", "N/A")

with col5:
    stops = driving_behavior.get("stop_count")
    if stops is not None:
        st.metric("Stops", f"{stops}")
    else:
        st.metric("Stops", "N/A")

with col6:
    start = datetime.fromisoformat(trip_info["start_time"].replace("Z", "+00:00"))
    st.metric("Date", start.strftime("%Y-%m-%d"))

# ===== SPEED RANGE BREAKDOWN =====
st.subheader("🚦 Speed Range Analysis")

if speed_ranges:
    col1, col2 = st.columns([1, 2])

    with col1:
        # Pie chart
        labels = []
        values = []
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']

        for idx, (range_name, data) in enumerate(speed_ranges.items()):
            labels.append(f"{range_name.title()}\n{data['percentage']:.1f}%")
            values.append(data['time'])

        fig_pie = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker=dict(colors=colors),
            hole=0.3
        )])
        fig_pie.update_layout(title="Time by Speed Range", height=350, margin=dict(t=40, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        # Bar chart with details
        range_data = []
        for range_name, data in speed_ranges.items():
            range_data.append({
                "Range": f"{range_name.title()} ({data['min']}-{data['max']} mph)",
                "Time (min)": data['time'] / 60,
                "Distance (mi)": data['distance'],
                "Percentage": data['percentage']
            })

        range_df = pd.DataFrame(range_data)

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=range_df["Range"],
            y=range_df["Time (min)"],
            name="Time (minutes)",
            marker_color='lightblue',
            yaxis='y'
        ))
        fig_bar.add_trace(go.Bar(
            x=range_df["Range"],
            y=range_df["Distance (mi)"],
            name="Distance (miles)",
            marker_color='lightgreen',
            yaxis='y2'
        ))

        fig_bar.update_layout(
            title="Speed Range Breakdown",
            yaxis=dict(title="Time (minutes)"),
            yaxis2=dict(title="Distance (miles)", overlaying='y', side='right'),
            barmode='group',
            height=350,
            margin=dict(t=40, b=0)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ===== FUEL & EFFICIENCY =====
st.subheader("⛽ Fuel & Efficiency")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    avg_mpg = fuel_economy.get("avg_mpg")
    if avg_mpg:
        st.metric("Avg MPG", f"{avg_mpg:.1f}")
    else:
        st.metric("Avg MPG", "N/A")

with col2:
    total_fuel = fuel_economy.get("total_fuel_gal")
    if total_fuel:
        st.metric("Fuel Used", f"{total_fuel:.2f} gal")
    else:
        st.metric("Fuel Used", "N/A")

with col3:
    efficiency_score = fuel_economy.get("efficiency_score")
    if efficiency_score:
        st.metric("Efficiency Score", f"{efficiency_score:.0f}%")
    else:
        st.metric("Efficiency Score", "N/A")

with col4:
    optimal_cruising = fuel_insights.get('optimal_cruising', {})
    optimal_mpg = optimal_cruising.get('avg_mpg', 0)
    if optimal_mpg:
        st.metric("Peak Efficiency MPG", f"{optimal_mpg:.1f}", delta="Optimal cruising", delta_color="normal")
    else:
        st.metric("Peak Efficiency MPG", "N/A")

with col5:
    idle_pct = time_breakdown.get("idle_percentage")
    if idle_pct is not None:
        st.metric("Idle Time", f"{idle_pct:.1f}%", delta=f"-{idle_pct:.1f}%", delta_color="inverse")
    else:
        st.metric("Idle Time", "N/A")

# ===== DRIVING BEHAVIOR =====
st.subheader("🚗 Driving Behavior & Throttle Analysis")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    driving_score = driving_behavior.get("driving_score")
    if driving_score is not None:
        st.metric("Driving Score", f"{driving_score:.0f}/100",
                 delta="Perfect!" if driving_score == 100 else None,
                 delta_color="normal")
    else:
        st.metric("Driving Score", "N/A")

with col2:
    event_counts = driving_behavior.get("event_counts", {})
    hard_events = event_counts.get("hard_brake", 0) + event_counts.get("hard_accel", 0)
    st.metric("Hard Events", f"{hard_events}")

with col3:
    if throttle_patterns:
        agg_score = throttle_patterns.get('aggressiveness_score', 0)
        st.metric("Aggressiveness", f"{agg_score:.0f}/100",
                 delta="Gentle" if agg_score < 30 else "Aggressive",
                 delta_color="inverse" if agg_score < 30 else "normal")
    else:
        st.metric("Aggressiveness", "N/A")

with col4:
    if throttle_patterns:
        avg_throttle = throttle_patterns.get('avg_throttle', 0)
        st.metric("Avg Throttle", f"{avg_throttle:.1f}%")
    else:
        st.metric("Avg Throttle", "N/A")

with col5:
    if throttle_patterns:
        dist = throttle_patterns.get('distribution', {})
        gentle_pct = dist.get('gentle_pct', 0)
        st.metric("Gentle Driving", f"{gentle_pct:.1f}%", delta="Good", delta_color="normal")
    else:
        st.metric("Gentle Driving", "N/A")

# Throttle distribution bar chart
if throttle_patterns:
    dist = throttle_patterns.get('distribution', {})
    dist_df = pd.DataFrame({
        "Category": ["Gentle (0-30%)", "Moderate (30-60%)", "Aggressive (60-80%)", "Very Aggressive (80-100%)"],
        "Percentage": [dist.get('gentle_pct', 0), dist.get('moderate_pct', 0),
                      dist.get('aggressive_pct', 0), dist.get('very_aggressive_pct', 0)],
        "Color": ['#2ECC71', '#3498DB', '#F39C12', '#E74C3C']
    })

    fig_throttle_dist = go.Figure(data=[
        go.Bar(x=dist_df["Category"], y=dist_df["Percentage"],
               marker_color=dist_df["Color"])
    ])
    fig_throttle_dist.update_layout(
        title="Throttle Input Distribution",
        yaxis_title="Percentage of Time (%)",
        height=300,
        margin=dict(t=40, b=60)
    )
    st.plotly_chart(fig_throttle_dist, use_container_width=True)

# ===== CRUISE CONTROL =====
if cruise_stats and cruise_stats.get('session_count', 0) > 0:
    st.subheader("🎛️ Cruise Control Usage")

    col1, col2, col3 = st.columns(3)

    with col1:
        total_cruise = cruise_stats.get('total_cruise_time', 0)
        st.metric("Total Cruise Time", f"{total_cruise / 60:.1f} min")

    with col2:
        session_count = cruise_stats.get('session_count', 0)
        st.metric("Cruise Sessions", f"{session_count}")

    with col3:
        avg_duration = cruise_stats.get('avg_session_duration', 0)
        st.metric("Avg Session Duration", f"{avg_duration / 60:.1f} min")

    # Cruise control timeline
    sessions = cruise_stats.get('sessions', [])
    if sessions:
        fig_timeline = go.Figure()

        for i, session in enumerate(sessions):
            duration = session['duration']
            avg_speed = session.get('avg_speed', 0)

            fig_timeline.add_trace(go.Bar(
                name=f"Session {i+1}",
                x=[duration],
                y=[f"{avg_speed:.0f} mph"],
                orientation='h',
                marker=dict(color=f'rgb({50 + i*20}, {100 + i*15}, {200 - i*10})'),
                text=f"{duration/60:.1f} min",
                textposition='inside',
                hovertemplate=f"Speed: {avg_speed:.1f} mph<br>Duration: {duration/60:.1f} min<extra></extra>"
            ))

        fig_timeline.update_layout(
            title="Cruise Control Sessions Timeline",
            xaxis_title="Duration (seconds)",
            yaxis_title="Average Speed",
            barmode='stack',
            showlegend=False,
            height=300,
            margin=dict(t=40, b=60)
        )
        st.plotly_chart(fig_timeline, use_container_width=True)

# Convert telemetry to DataFrame
df = pd.DataFrame(telemetry["data"])
if df.empty:
    st.warning("No telemetry data available for this trip.")
    st.stop()

# Expand sensors column
if "sensors" in df.columns:
    sensors_df = pd.json_normalize(df["sensors"])
    df = pd.concat([df.drop("sensors", axis=1), sensors_df], axis=1)

# ===== PERFORMANCE CHARTS =====
st.subheader("📈 Speed & Performance")

# Create 2x2 subplot grid
fig = make_subplots(
    rows=2, cols=2,
    subplot_titles=("Speed Over Time", "Engine RPM", "Throttle Position", "Fuel Economy"),
    specs=[[{"secondary_y": False}, {"secondary_y": False}],
           [{"secondary_y": False}, {"secondary_y": False}]]
)

# Speed
if "speed_mph" in df.columns:
    fig.add_trace(
        go.Scatter(x=df["elapsed_seconds"], y=df["speed_mph"], name="Speed", line=dict(color="blue")),
        row=1, col=1
    )

# RPM
if "engine_rpm" in df.columns:
    fig.add_trace(
        go.Scatter(x=df["elapsed_seconds"], y=df["engine_rpm"], name="RPM", line=dict(color="red")),
        row=1, col=2
    )

# Throttle
if "throttle_position_pct" in df.columns:
    fig.add_trace(
        go.Scatter(x=df["elapsed_seconds"], y=df["throttle_position_pct"], name="Throttle", line=dict(color="green")),
        row=2, col=1
    )

# Fuel Economy
if "instant_mpg" in df.columns:
    # Filter out unrealistic MPG values
    mpg_filtered = df[df["instant_mpg"] < 100]["instant_mpg"]
    elapsed_filtered = df[df["instant_mpg"] < 100]["elapsed_seconds"]
    fig.add_trace(
        go.Scatter(x=elapsed_filtered, y=mpg_filtered, name="MPG", line=dict(color="purple")),
        row=2, col=2
    )

fig.update_xaxes(title_text="Time (seconds)", row=1, col=1)
fig.update_xaxes(title_text="Time (seconds)", row=1, col=2)
fig.update_xaxes(title_text="Time (seconds)", row=2, col=1)
fig.update_xaxes(title_text="Time (seconds)", row=2, col=2)

fig.update_yaxes(title_text="MPH", row=1, col=1)
fig.update_yaxes(title_text="RPM", row=1, col=2)
fig.update_yaxes(title_text="%", row=2, col=1)
fig.update_yaxes(title_text="MPG", row=2, col=2)

fig.update_layout(height=700, showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# ===== THROTTLE HEAT MAP =====
st.subheader("🔥 Throttle Position Heat Map")
if "throttle_position_pct" in df.columns:
    # Create bins for time and throttle
    time_bins = 50
    throttle_bins = 20

    df_throttle = df[df["throttle_position_pct"].notna()].copy()

    if len(df_throttle) > 0:
        df_throttle["time_bin"] = pd.cut(df_throttle["elapsed_seconds"], bins=time_bins)
        df_throttle["throttle_bin"] = pd.cut(df_throttle["throttle_position_pct"], bins=throttle_bins)

        # Create heatmap data
        heatmap_data = df_throttle.groupby(["time_bin", "throttle_bin"]).size().reset_index(name='count')

        # Pivot for heatmap
        pivot_data = heatmap_data.pivot_table(
            index='throttle_bin',
            columns='time_bin',
            values='count',
            fill_value=0
        )

        fig_heatmap = go.Figure(data=go.Heatmap(
            z=pivot_data.values,
            colorscale='YlOrRd',
            showscale=True
        ))
        fig_heatmap.update_layout(
            title="Throttle Position Intensity Over Trip",
            xaxis_title="Trip Progress →",
            yaxis_title="Throttle Position (%) ↑",
            height=300,
            margin=dict(t=40, b=60)
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)

# ===== COLOR-CODED ROUTE MAP =====
st.subheader("🗺️ Route Map (Color-Coded by Speed)")

gps_points = gps_data.get("points", [])
events = events_data.get("events", [])

if len(df) > 0:
    # Filter to points with valid GPS
    df_gps = df[(df['latitude'].notna()) & (df['longitude'].notna()) & (df['latitude'] != 0)].copy()

    if not df_gps.empty:
        # Calculate center
        center_lat = df_gps['latitude'].mean()
        center_lng = df_gps['longitude'].mean()

        # Create map
        m = folium.Map(location=[center_lat, center_lng], zoom_start=12)

        # Add colored route segments
        for i in range(len(df_gps) - 1):
            if i % 10 != 0:  # Downsample for performance
                continue

            row1 = df_gps.iloc[i]
            row2 = df_gps.iloc[i + 1]

            speed = row1.get('speed_mph', 0)

            # Color based on speed
            if speed < 20:
                color = '#FF0000'  # Red - slow/stopped
            elif speed < 40:
                color = '#FF8800'  # Orange - city
            elif speed < 60:
                color = '#FFFF00'  # Yellow - suburban
            else:
                color = '#00FF00'  # Green - highway

            folium.PolyLine(
                locations=[[row1['latitude'], row1['longitude']],
                          [row2['latitude'], row2['longitude']]],
                color=color,
                weight=3,
                opacity=0.7
            ).add_to(m)

        # Add markers for stops/slowdowns
        stop_events = [e for e in events if e.get('type') == 'idle_start']
        for event in stop_events:
            if event.get('latitude') and event.get('longitude'):
                duration = event.get('metadata', {}).get('duration_seconds', 0)
                folium.CircleMarker(
                    location=[event['latitude'], event['longitude']],
                    radius=8,
                    popup=f"Stop: {duration:.0f}s",
                    color='red',
                    fill=True,
                    fillColor='red',
                    fillOpacity=0.6
                ).add_to(m)

        # Add start/end markers
        first_row = df_gps.iloc[0]
        last_row = df_gps.iloc[-1]

        folium.Marker(
            [first_row['latitude'], first_row['longitude']],
            popup="Start",
            icon=folium.Icon(color="green", icon="play")
        ).add_to(m)

        folium.Marker(
            [last_row['latitude'], last_row['longitude']],
            popup="End",
            icon=folium.Icon(color="red", icon="stop")
        ).add_to(m)

        # Add legend
        legend_html = '''
        <div style="position: fixed;
                    bottom: 50px; right: 50px; width: 180px; height: 160px;
                    background-color: white; border:2px solid grey; z-index:9999;
                    font-size:14px; padding: 10px">
        <p style="margin:0"><b>Speed Legend:</b></p>
        <p style="margin:5px 0"><span style="color:#FF0000">━━━</span> 0-20 mph (Stopped/Slow)</p>
        <p style="margin:5px 0"><span style="color:#FF8800">━━━</span> 20-40 mph (City)</p>
        <p style="margin:5px 0"><span style="color:#FFFF00">━━━</span> 40-60 mph (Suburban)</p>
        <p style="margin:5px 0"><span style="color:#00FF00">━━━</span> 60+ mph (Highway)</p>
        <p style="margin:5px 0"><span style="color:#FF0000">●</span> Stops/Slowdowns</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))

        st_folium(m, width=None, height=600, use_container_width=True)
    else:
        st.info("No GPS data with valid coordinates available for route visualization.")
else:
    st.info("No GPS data available for route visualization.")

# Raw data section
with st.expander("📊 View Raw Data"):
    st.dataframe(df, height=400)
