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

if "dashboard_trip_id" not in st.session_state:
    st.session_state.dashboard_trip_id = st.session_state.get("selected_trip_id", trips[0]["id"])

selected_trip_id = st.selectbox(
    "Select Trip",
    options=list(trip_options.keys()),
    format_func=lambda x: trip_options[x],
    index=list(trip_options.keys()).index(st.session_state.dashboard_trip_id) if st.session_state.dashboard_trip_id in trip_options else 0,
    key="dashboard_trip_selector",
)

st.session_state.dashboard_trip_id = selected_trip_id

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
cold_start = advanced.get("cold_start", {})

# Convert telemetry to DataFrame early (needed by multiple sections)
df = pd.DataFrame(telemetry["data"])
if df.empty:
    st.warning("No telemetry data available for this trip.")
    st.stop()

# Expand sensors column
if "sensors" in df.columns:
    sensors_df = pd.json_normalize(df["sensors"])
    df = pd.concat([df.drop("sensors", axis=1), sensors_df], axis=1)

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

# ===== COLD START IMPACT =====
if cold_start and cold_start.get("cold_samples", 0) > 0 and cold_start.get("warm_samples", 0) > 0:
    st.subheader("🌡️ Cold Start Impact")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Cold MPG (first 5 min)", f"{cold_start['cold_avg_mpg']:.1f}")
    with col2:
        st.metric("Warm MPG (after 5 min)", f"{cold_start['warm_avg_mpg']:.1f}")
    with col3:
        penalty = cold_start.get('mpg_penalty_pct', 0)
        st.metric("Cold Start Penalty", f"{penalty:.1f}%",
                  delta=f"-{penalty:.1f}% MPG", delta_color="inverse")
    with col4:
        cold_temp = cold_start.get('cold_start_temp_f')
        if cold_temp:
            st.metric("Starting Coolant Temp", f"{cold_temp:.0f}°F")
        else:
            st.metric("Starting Coolant Temp", "N/A")

    # Cold start chart: coolant temp + MPG over first 10 minutes
    df_cold = df[df["elapsed_seconds"] <= 600].copy()
    has_coolant = "engine_coolant_temp_f" in df_cold.columns and df_cold["engine_coolant_temp_f"].notna().any()
    has_mpg = "instant_mpg" in df_cold.columns and df_cold["instant_mpg"].notna().any()

    if has_coolant or has_mpg:
        fig_cold = make_subplots(specs=[[{"secondary_y": True}]])

        if has_coolant:
            df_coolant = df_cold[df_cold["engine_coolant_temp_f"].notna()]
            fig_cold.add_trace(
                go.Scatter(x=df_coolant["elapsed_seconds"] / 60, y=df_coolant["engine_coolant_temp_f"],
                           name="Coolant Temp (°F)", line=dict(color="#FF6B6B", width=2)),
                secondary_y=False
            )

        if has_mpg:
            df_mpg_cold = df_cold[(df_cold["instant_mpg"].notna()) & (df_cold["instant_mpg"] < 100) & (df_cold["speed_mph"] > 5)]
            if not df_mpg_cold.empty:
                # Rolling average for smoother visualization
                df_mpg_cold = df_mpg_cold.copy()
                df_mpg_cold["mpg_smooth"] = df_mpg_cold["instant_mpg"].rolling(window=20, min_periods=1).mean()
                fig_cold.add_trace(
                    go.Scatter(x=df_mpg_cold["elapsed_seconds"] / 60, y=df_mpg_cold["mpg_smooth"],
                               name="MPG (smoothed)", line=dict(color="#4ECDC4", width=2)),
                    secondary_y=True
                )

        # Add 5-minute marker
        fig_cold.add_vline(x=5, line_dash="dash", line_color="gray", annotation_text="Warmup threshold")

        fig_cold.update_layout(title="Cold Start: Coolant Temperature & Fuel Economy (First 10 Minutes)",
                               height=350, margin=dict(t=40, b=40))
        fig_cold.update_xaxes(title_text="Time (minutes)")
        fig_cold.update_yaxes(title_text="Coolant Temp (°F)", secondary_y=False)
        fig_cold.update_yaxes(title_text="MPG", secondary_y=True)
        st.plotly_chart(fig_cold, use_container_width=True)

# ===== ENGINE LOAD EFFICIENCY =====
has_load = "calculated_load_pct" in df.columns and df["calculated_load_pct"].notna().any()
has_mpg_data = "instant_mpg" in df.columns and df["instant_mpg"].notna().any()

if has_load and has_mpg_data:
    st.subheader("⚙️ Engine Load vs Fuel Efficiency")

    df_eff = df[(df["calculated_load_pct"].notna()) & (df["instant_mpg"].notna()) &
                (df["instant_mpg"] > 0) & (df["instant_mpg"] < 100) &
                (df["speed_mph"] > 5)].copy()

    if not df_eff.empty:
        col1, col2 = st.columns(2)

        with col1:
            fig_load = px.scatter(
                df_eff, x="calculated_load_pct", y="instant_mpg",
                color="speed_mph", color_continuous_scale="Viridis",
                labels={"calculated_load_pct": "Engine Load (%)", "instant_mpg": "Instant MPG",
                        "speed_mph": "Speed (mph)"},
                title="Engine Load vs MPG (colored by speed)",
                opacity=0.4
            )
            fig_load.update_layout(height=400, margin=dict(t=40, b=40))
            st.plotly_chart(fig_load, use_container_width=True)

        with col2:
            # Altitude + MPG overlay
            has_altitude = "altitude_ft" in df.columns and df["altitude_ft"].notna().any()
            if has_altitude:
                df_alt = df[(df["altitude_ft"].notna()) & (df["altitude_ft"] != 0)].copy()
                df_mpg_alt = df[(df["instant_mpg"].notna()) & (df["instant_mpg"] > 0) &
                                (df["instant_mpg"] < 100) & (df["speed_mph"] > 5)].copy()

                fig_alt = make_subplots(specs=[[{"secondary_y": True}]])

                if not df_alt.empty:
                    fig_alt.add_trace(
                        go.Scatter(x=df_alt["elapsed_seconds"] / 60, y=df_alt["altitude_ft"],
                                   name="Altitude (ft)", fill="tozeroy",
                                   line=dict(color="rgba(69,183,209,0.6)"),
                                   fillcolor="rgba(69,183,209,0.15)"),
                        secondary_y=False
                    )

                if not df_mpg_alt.empty:
                    df_mpg_alt["mpg_smooth"] = df_mpg_alt["instant_mpg"].rolling(window=30, min_periods=1).mean()
                    fig_alt.add_trace(
                        go.Scatter(x=df_mpg_alt["elapsed_seconds"] / 60, y=df_mpg_alt["mpg_smooth"],
                                   name="MPG (smoothed)", line=dict(color="#E74C3C", width=2)),
                        secondary_y=True
                    )

                fig_alt.update_layout(title="Altitude Profile & Fuel Economy", height=400, margin=dict(t=40, b=40))
                fig_alt.update_xaxes(title_text="Time (minutes)")
                fig_alt.update_yaxes(title_text="Altitude (ft)", secondary_y=False)
                fig_alt.update_yaxes(title_text="MPG", secondary_y=True)
                st.plotly_chart(fig_alt, use_container_width=True)
            else:
                # If no altitude data, show load histogram instead
                fig_hist = px.histogram(df_eff, x="calculated_load_pct", nbins=30,
                                        title="Engine Load Distribution",
                                        labels={"calculated_load_pct": "Engine Load (%)"})
                fig_hist.update_layout(height=400, margin=dict(t=40, b=40))
                st.plotly_chart(fig_hist, use_container_width=True)

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

# Throttle distribution bar chart + Throttle vs Acceleration scatter
col_left, col_right = st.columns(2)

with col_left:
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
            height=400,
            margin=dict(t=40, b=60)
        )
        st.plotly_chart(fig_throttle_dist, use_container_width=True)

with col_right:
    # Throttle vs Acceleration Scatter
    has_pedal = "accelerator_pedal_position_pct" in df.columns and df["accelerator_pedal_position_pct"].notna().any()
    has_accel = "acceleration_g" in df.columns and df["acceleration_g"].notna().any()

    if has_pedal and has_accel:
        df_ta = df[(df["accelerator_pedal_position_pct"].notna()) &
                   (df["acceleration_g"].notna()) &
                   (df["speed_mph"] > 5)].copy()

        if not df_ta.empty:
            fig_ta = px.scatter(
                df_ta, x="accelerator_pedal_position_pct", y="acceleration_g",
                color="speed_mph", color_continuous_scale="Plasma",
                labels={"accelerator_pedal_position_pct": "Pedal Position (%)",
                        "acceleration_g": "Acceleration (g)",
                        "speed_mph": "Speed (mph)"},
                title="Pedal Input vs Actual Acceleration",
                opacity=0.3
            )
            fig_ta.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig_ta.update_layout(height=400, margin=dict(t=40, b=60))
            st.plotly_chart(fig_ta, use_container_width=True)
    elif not has_pedal and has_accel and "throttle_position_pct" in df.columns:
        # Fallback to throttle position if no pedal data
        df_ta = df[(df["throttle_position_pct"].notna()) &
                   (df["acceleration_g"].notna()) &
                   (df["speed_mph"] > 5)].copy()

        if not df_ta.empty:
            fig_ta = px.scatter(
                df_ta, x="throttle_position_pct", y="acceleration_g",
                color="speed_mph", color_continuous_scale="Plasma",
                labels={"throttle_position_pct": "Throttle Position (%)",
                        "acceleration_g": "Acceleration (g)",
                        "speed_mph": "Speed (mph)"},
                title="Throttle Position vs Actual Acceleration",
                opacity=0.3
            )
            fig_ta.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig_ta.update_layout(height=400, margin=dict(t=40, b=60))
            st.plotly_chart(fig_ta, use_container_width=True)

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

# ===== CVT RATIO PLOT =====
has_rpm = "engine_rpm" in df.columns and df["engine_rpm"].notna().any()
has_speed = "speed_mph" in df.columns and df["speed_mph"].notna().any()

if has_rpm and has_speed:
    st.subheader("🔄 CVT Ratio Analysis")

    df_cvt = df[(df["engine_rpm"].notna()) & (df["speed_mph"] > 5) &
                (df["engine_rpm"] > 500)].copy()

    if not df_cvt.empty:
        col1, col2 = st.columns(2)

        with col1:
            fig_cvt = px.scatter(
                df_cvt, x="speed_mph", y="engine_rpm",
                color="throttle_position_pct" if "throttle_position_pct" in df_cvt.columns else None,
                color_continuous_scale="YlOrRd",
                labels={"speed_mph": "Vehicle Speed (mph)", "engine_rpm": "Engine RPM",
                        "throttle_position_pct": "Throttle (%)"},
                title="CVT Ratio Map: RPM vs Speed",
                opacity=0.3
            )
            fig_cvt.update_layout(height=450, margin=dict(t=40, b=40))
            st.plotly_chart(fig_cvt, use_container_width=True)

        with col2:
            # CVT internals if available (NIN/NOUT from sensors)
            has_nin = "speed_of_nin" in df.columns and df["speed_of_nin"].notna().any()
            has_nout = "speed_of_nout" in df.columns and df["speed_of_nout"].notna().any()

            if has_nin and has_nout:
                df_cvt_int = df[(df["speed_of_nin"].notna()) & (df["speed_of_nout"].notna()) &
                                (df["speed_of_nout"] > 0)].copy()
                if not df_cvt_int.empty:
                    df_cvt_int["cvt_ratio"] = df_cvt_int["speed_of_nin"] / df_cvt_int["speed_of_nout"]

                    fig_cvt_ratio = make_subplots(rows=2, cols=1,
                                                   subplot_titles=("CVT Input/Output Shaft Speeds", "CVT Ratio"),
                                                   shared_xaxes=True)

                    fig_cvt_ratio.add_trace(
                        go.Scatter(x=df_cvt_int["elapsed_seconds"] / 60, y=df_cvt_int["speed_of_nin"],
                                   name="NIN (Input)", line=dict(color="#E74C3C")),
                        row=1, col=1
                    )
                    fig_cvt_ratio.add_trace(
                        go.Scatter(x=df_cvt_int["elapsed_seconds"] / 60, y=df_cvt_int["speed_of_nout"],
                                   name="NOUT (Output)", line=dict(color="#3498DB")),
                        row=1, col=1
                    )
                    fig_cvt_ratio.add_trace(
                        go.Scatter(x=df_cvt_int["elapsed_seconds"] / 60, y=df_cvt_int["cvt_ratio"],
                                   name="Ratio", line=dict(color="#2ECC71")),
                        row=2, col=1
                    )

                    fig_cvt_ratio.update_layout(height=450, margin=dict(t=40, b=40))
                    fig_cvt_ratio.update_xaxes(title_text="Time (minutes)", row=2, col=1)
                    fig_cvt_ratio.update_yaxes(title_text="RPM", row=1, col=1)
                    fig_cvt_ratio.update_yaxes(title_text="Ratio (NIN/NOUT)", row=2, col=1)
                    st.plotly_chart(fig_cvt_ratio, use_container_width=True)
            else:
                # Show RPM vs Speed density if no CVT internals
                df_cvt["rpm_per_mph"] = df_cvt["engine_rpm"] / df_cvt["speed_mph"]
                fig_eff_zone = px.histogram(df_cvt, x="rpm_per_mph", nbins=50,
                                            title="RPM/MPH Distribution (lower = more efficient)",
                                            labels={"rpm_per_mph": "RPM per MPH"})
                fig_eff_zone.update_layout(height=450, margin=dict(t=40, b=40))
                st.plotly_chart(fig_eff_zone, use_container_width=True)

# ===== TOYOTA CVT HEALTH =====
has_at_oil = "a_t_oil_temperature_1" in df.columns and df["a_t_oil_temperature_1"].notna().any()
_vvt_col = "vvt_ex_chg_angle_bank1" if "vvt_ex_chg_angle_bank1" in df.columns else "vvt_ex_chg_angle"
has_vvt = _vvt_col in df.columns and df[_vvt_col].notna().any()
has_knock = "knock_feedback_value" in df.columns and df["knock_feedback_value"].notna().any()
has_fuel_cut = "fuel_cut_condition" in df.columns and df["fuel_cut_condition"].notna().any()
has_short_ft = "short_ft_b1s1" in df.columns and df["short_ft_b1s1"].notna().any()
has_long_ft = "long_ft_b1s1" in df.columns and df["long_ft_b1s1"].notna().any()

if has_at_oil or has_vvt or has_knock or has_fuel_cut or has_short_ft or has_long_ft:
    st.subheader("🏭 Engine & CVT Health (Toyota ECT)")

    num_subplots = int(sum([has_at_oil, has_vvt, has_knock or has_fuel_cut, has_short_ft or has_long_ft]))
    if num_subplots > 0:
        titles = []
        if has_at_oil:
            titles.append("A/T Oil Temperature")
        if has_vvt:
            titles.append("VVT Exhaust Cam Angle")
        if has_knock or has_fuel_cut:
            titles.append("Knock & Fuel Cut")
        if has_short_ft or has_long_ft:
            titles.append("Fuel Trims (B1S1)")

        fig_toyota = make_subplots(rows=num_subplots, cols=1, subplot_titles=titles,
                                    shared_xaxes=True, vertical_spacing=0.08)
        row_idx = 1

        if has_at_oil:
            df_oil = df[df["a_t_oil_temperature_1"].notna()]
            fig_toyota.add_trace(
                go.Scatter(x=df_oil["elapsed_seconds"] / 60, y=df_oil["a_t_oil_temperature_1"],
                           name="A/T Oil Temp (°F)", line=dict(color="#E74C3C")),
                row=row_idx, col=1
            )
            fig_toyota.update_yaxes(title_text="°F", row=row_idx, col=1)
            row_idx += 1

        if has_vvt:
            df_vvt = df[df[_vvt_col].notna()]
            fig_toyota.add_trace(
                go.Scatter(x=df_vvt["elapsed_seconds"] / 60, y=df_vvt["vvt_ex_chg_angle_bank1"],
                           name="VVT Angle (deg)", line=dict(color="#9B59B6")),
                row=row_idx, col=1
            )
            fig_toyota.update_yaxes(title_text="Degrees", row=row_idx, col=1)
            row_idx += 1

        if has_knock or has_fuel_cut:
            if has_knock:
                df_knock = df[df["knock_feedback_value"].notna()]
                fig_toyota.add_trace(
                    go.Scatter(x=df_knock["elapsed_seconds"] / 60, y=df_knock["knock_feedback_value"],
                               name="Knock Feedback (deg)", line=dict(color="#F39C12")),
                    row=row_idx, col=1
                )
            if has_fuel_cut:
                df_fc = df[df["fuel_cut_condition"].notna()]
                fig_toyota.add_trace(
                    go.Scatter(x=df_fc["elapsed_seconds"] / 60, y=df_fc["fuel_cut_condition"],
                               name="Fuel Cut", line=dict(color="#1ABC9C"), opacity=0.7),
                    row=row_idx, col=1
                )
            fig_toyota.update_yaxes(title_text="Value", row=row_idx, col=1)
            row_idx += 1

        if has_short_ft or has_long_ft:
            if has_short_ft:
                df_sft = df[df["short_ft_b1s1"].notna()]
                fig_toyota.add_trace(
                    go.Scatter(x=df_sft["elapsed_seconds"] / 60, y=df_sft["short_ft_b1s1"],
                               name="Short FT B1S1 (%)", line=dict(color="#3498DB")),
                    row=row_idx, col=1
                )
            if has_long_ft:
                df_lft = df[df["long_ft_b1s1"].notna()]
                fig_toyota.add_trace(
                    go.Scatter(x=df_lft["elapsed_seconds"] / 60, y=df_lft["long_ft_b1s1"],
                               name="Long FT B1S1 (%)", line=dict(color="#E67E22")),
                    row=row_idx, col=1
                )
            fig_toyota.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4, row=row_idx, col=1)
            fig_toyota.update_yaxes(title_text="%", row=row_idx, col=1)

        fig_toyota.update_xaxes(title_text="Time (minutes)", row=num_subplots, col=1)
        fig_toyota.update_layout(height=250 * num_subplots, margin=dict(t=40, b=40))
        st.plotly_chart(fig_toyota, use_container_width=True)

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

# ===== VEHICLE DYNAMICS =====
has_lateral_g = "lateral_g" in df.columns and df["lateral_g"].notna().any()
has_fwd_g = "forward_and_rearward_g" in df.columns and df["forward_and_rearward_g"].notna().any()
has_yaw = "yaw_rate_sensor" in df.columns and df["yaw_rate_sensor"].notna().any()
has_steering = "steering_angle_sensor" in df.columns and df["steering_angle_sensor"].notna().any()

if has_lateral_g or has_fwd_g or has_yaw:
    st.subheader("🏎️ Vehicle Dynamics")

    col1, col2 = st.columns(2)

    with col1:
        # G-Force Friction Circle
        if has_lateral_g and has_fwd_g:
            df_g = df[(df["lateral_g"].notna()) & (df["forward_and_rearward_g"].notna())].copy()
            # Convert ft/s² to g
            df_g["lateral_g_force"] = df_g["lateral_g"] / 32.174
            df_g["longitudinal_g_force"] = df_g["forward_and_rearward_g"] / 32.174

            if not df_g.empty:
                fig_friction = px.scatter(
                    df_g, x="lateral_g_force", y="longitudinal_g_force",
                    color="speed_mph" if "speed_mph" in df_g.columns else None,
                    color_continuous_scale="Turbo",
                    labels={"lateral_g_force": "Lateral G (+ = right)",
                            "longitudinal_g_force": "Longitudinal G (+ = accel)",
                            "speed_mph": "Speed (mph)"},
                    title="G-Force Friction Circle",
                    opacity=0.3
                )
                # Add reference circles
                theta = np.linspace(0, 2 * np.pi, 100)
                for r in [0.2, 0.4, 0.6]:
                    fig_friction.add_trace(go.Scatter(
                        x=r * np.cos(theta), y=r * np.sin(theta),
                        mode='lines', line=dict(color='gray', dash='dot', width=1),
                        showlegend=False, hoverinfo='skip'
                    ))
                fig_friction.add_hline(y=0, line_color="gray", opacity=0.3)
                fig_friction.add_vline(x=0, line_color="gray", opacity=0.3)
                fig_friction.update_layout(height=450, margin=dict(t=40, b=40),
                                           yaxis=dict(scaleanchor="x", scaleratio=1))
                st.plotly_chart(fig_friction, use_container_width=True)

    with col2:
        # Vehicle Stability: Yaw + Steering + Lateral G
        stability_traces = int(sum([has_yaw, has_steering, has_lateral_g]))
        if stability_traces >= 2:
            fig_stab = make_subplots(rows=stability_traces, cols=1,
                                      shared_xaxes=True, vertical_spacing=0.08,
                                      subplot_titles=[t for t, h in
                                                       [("Yaw Rate", has_yaw),
                                                        ("Steering Angle", has_steering),
                                                        ("Lateral G", has_lateral_g)] if h])
            s_row = 1

            if has_yaw:
                df_yaw = df[df["yaw_rate_sensor"].notna()]
                fig_stab.add_trace(
                    go.Scatter(x=df_yaw["elapsed_seconds"] / 60, y=df_yaw["yaw_rate_sensor"],
                               name="Yaw Rate (deg/s)", line=dict(color="#E74C3C")),
                    row=s_row, col=1
                )
                fig_stab.update_yaxes(title_text="deg/s", row=s_row, col=1)
                s_row += 1

            if has_steering:
                df_steer = df[df["steering_angle_sensor"].notna()]
                fig_stab.add_trace(
                    go.Scatter(x=df_steer["elapsed_seconds"] / 60, y=df_steer["steering_angle_sensor"],
                               name="Steering Angle (deg)", line=dict(color="#3498DB")),
                    row=s_row, col=1
                )
                fig_stab.update_yaxes(title_text="deg", row=s_row, col=1)
                s_row += 1

            if has_lateral_g:
                df_lat = df[df["lateral_g"].notna()].copy()
                df_lat["lateral_g_force"] = df_lat["lateral_g"] / 32.174
                fig_stab.add_trace(
                    go.Scatter(x=df_lat["elapsed_seconds"] / 60, y=df_lat["lateral_g_force"],
                               name="Lateral G", line=dict(color="#2ECC71")),
                    row=s_row, col=1
                )
                fig_stab.update_yaxes(title_text="g", row=s_row, col=1)

            fig_stab.update_xaxes(title_text="Time (minutes)", row=stability_traces, col=1)
            fig_stab.update_layout(height=150 * stability_traces + 100, margin=dict(t=40, b=40))
            st.plotly_chart(fig_stab, use_container_width=True)

# ===== WHEEL SPEED ANALYSIS =====
wheel_cols = ["fl_wheel_speed", "fr_wheel_speed", "rl_wheel_speed", "rr_wheel_speed"]
has_wheels = all(c in df.columns and df[c].notna().any() for c in wheel_cols)

if has_wheels:
    st.subheader("🛞 Wheel Speed Analysis")

    df_wheels = df[df[wheel_cols[0]].notna()].copy()

    if not df_wheels.empty:
        col1, col2 = st.columns(2)

        with col1:
            fig_ws = go.Figure()
            wheel_colors = {"fl_wheel_speed": "#E74C3C", "fr_wheel_speed": "#3498DB",
                            "rl_wheel_speed": "#2ECC71", "rr_wheel_speed": "#F39C12"}
            wheel_labels = {"fl_wheel_speed": "FL", "fr_wheel_speed": "FR",
                            "rl_wheel_speed": "RL", "rr_wheel_speed": "RR"}

            for col_name in wheel_cols:
                fig_ws.add_trace(go.Scatter(
                    x=df_wheels["elapsed_seconds"] / 60, y=df_wheels[col_name],
                    name=wheel_labels[col_name], line=dict(color=wheel_colors[col_name], width=1),
                    opacity=0.7
                ))

            fig_ws.update_layout(title="Individual Wheel Speeds", height=400,
                                  xaxis_title="Time (minutes)", yaxis_title="Speed (mph)",
                                  margin=dict(t=40, b=40))
            st.plotly_chart(fig_ws, use_container_width=True)

        with col2:
            # Wheel speed differential (front avg vs rear avg)
            df_wheels["front_avg"] = (df_wheels["fl_wheel_speed"] + df_wheels["fr_wheel_speed"]) / 2
            df_wheels["rear_avg"] = (df_wheels["rl_wheel_speed"] + df_wheels["rr_wheel_speed"]) / 2
            df_wheels["lr_diff"] = df_wheels["fl_wheel_speed"] - df_wheels["fr_wheel_speed"]
            df_wheels["fr_diff"] = df_wheels["front_avg"] - df_wheels["rear_avg"]

            fig_diff = make_subplots(rows=2, cols=1,
                                      subplot_titles=("Front-Rear Speed Difference", "Left-Right Speed Difference (Front)"),
                                      shared_xaxes=True)

            fig_diff.add_trace(
                go.Scatter(x=df_wheels["elapsed_seconds"] / 60, y=df_wheels["fr_diff"],
                           name="Front - Rear", line=dict(color="#E74C3C", width=1)),
                row=1, col=1
            )
            fig_diff.add_trace(
                go.Scatter(x=df_wheels["elapsed_seconds"] / 60, y=df_wheels["lr_diff"],
                           name="FL - FR", line=dict(color="#3498DB", width=1)),
                row=2, col=1
            )

            fig_diff.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4, row=1, col=1)
            fig_diff.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4, row=2, col=1)
            fig_diff.update_xaxes(title_text="Time (minutes)", row=2, col=1)
            fig_diff.update_yaxes(title_text="MPH diff", row=1, col=1)
            fig_diff.update_yaxes(title_text="MPH diff", row=2, col=1)
            fig_diff.update_layout(height=400, margin=dict(t=40, b=40))
            st.plotly_chart(fig_diff, use_container_width=True)

# ===== TIRE PRESSURE & TEMPERATURE =====
tire_pressure_cols = [f"id_{i}_tire_inflation_pressure" for i in range(1, 5)]
tire_temp_cols = [f"id_{i}_temperature_in_tire" for i in range(1, 5)]
has_tire_pressure = any(c in df.columns and df[c].notna().any() for c in tire_pressure_cols)
has_tire_temp = any(c in df.columns and df[c].notna().any() for c in tire_temp_cols)

if has_tire_pressure or has_tire_temp:
    st.subheader("🔧 Tire Pressure & Temperature")

    col1, col2 = st.columns(2)

    with col1:
        if has_tire_pressure:
            fig_tp = go.Figure()
            tire_colors = ["#E74C3C", "#3498DB", "#2ECC71", "#F39C12"]
            tire_labels = ["FL", "FR", "RL", "RR"]

            for i, (col_name, color, label) in enumerate(zip(tire_pressure_cols, tire_colors, tire_labels)):
                if col_name in df.columns and df[col_name].notna().any():
                    df_tp = df[df[col_name].notna()]
                    fig_tp.add_trace(go.Scatter(
                        x=df_tp["elapsed_seconds"] / 60, y=df_tp[col_name],
                        name=label, line=dict(color=color, width=2)
                    ))

            # Add recommended pressure range
            fig_tp.add_hline(y=32, line_dash="dash", line_color="gray", opacity=0.4,
                             annotation_text="Min recommended (32 psi)")
            fig_tp.update_layout(title="Tire Inflation Pressure", height=350,
                                  xaxis_title="Time (minutes)", yaxis_title="Pressure (psi)",
                                  margin=dict(t=40, b=40))
            st.plotly_chart(fig_tp, use_container_width=True)

    with col2:
        if has_tire_temp:
            fig_tt = go.Figure()
            for i, (col_name, color, label) in enumerate(zip(tire_temp_cols, tire_colors, tire_labels)):
                if col_name in df.columns and df[col_name].notna().any():
                    df_tt = df[df[col_name].notna()]
                    fig_tt.add_trace(go.Scatter(
                        x=df_tt["elapsed_seconds"] / 60, y=df_tt[col_name],
                        name=label, line=dict(color=color, width=2)
                    ))

            fig_tt.update_layout(title="Tire Temperature", height=350,
                                  xaxis_title="Time (minutes)", yaxis_title="Temperature (°F)",
                                  margin=dict(t=40, b=40))
            st.plotly_chart(fig_tt, use_container_width=True)

    # Tire pressure summary metrics
    if has_tire_pressure:
        cols = st.columns(4)
        for i, (col_name, label) in enumerate(zip(tire_pressure_cols, tire_labels)):
            with cols[i]:
                if col_name in df.columns and df[col_name].notna().any():
                    current = df[df[col_name].notna()][col_name].iloc[-1]
                    avg_val = df[df[col_name].notna()][col_name].mean()
                    st.metric(f"{label} Pressure", f"{current:.1f} psi",
                              delta=f"avg {avg_val:.1f}" if abs(current - avg_val) > 0.5 else None)

# ===== STEERING & EPS =====
has_steer_torque = "steering_wheel_torque" in df.columns and df["steering_wheel_torque"].notna().any()
has_eps_current = "motor_actual_current" in df.columns and df["motor_actual_current"].notna().any()

if has_steer_torque or has_eps_current:
    st.subheader("🎯 Steering & Electric Power Steering")

    col1, col2 = st.columns(2)

    with col1:
        if has_steer_torque:
            fig_torque = go.Figure()

            df_torque = df[df["steering_wheel_torque"].notna()].copy()

            if has_eps_current:
                fig_torque = make_subplots(rows=2, cols=1,
                                            subplot_titles=("Steering Wheel Torque", "EPS Motor Current"),
                                            shared_xaxes=True)
                fig_torque.add_trace(
                    go.Scatter(x=df_torque["elapsed_seconds"] / 60, y=df_torque["steering_wheel_torque"],
                               name="Torque (lb-ft)", line=dict(color="#9B59B6", width=1)),
                    row=1, col=1
                )
                df_eps = df[df["motor_actual_current"].notna()]
                fig_torque.add_trace(
                    go.Scatter(x=df_eps["elapsed_seconds"] / 60, y=df_eps["motor_actual_current"],
                               name="EPS Current (A)", line=dict(color="#E67E22", width=1)),
                    row=2, col=1
                )
                fig_torque.update_xaxes(title_text="Time (minutes)", row=2, col=1)
                fig_torque.update_yaxes(title_text="lb-ft", row=1, col=1)
                fig_torque.update_yaxes(title_text="Amps", row=2, col=1)
                fig_torque.update_layout(height=400, margin=dict(t=40, b=40))
            else:
                fig_torque.add_trace(
                    go.Scatter(x=df_torque["elapsed_seconds"] / 60, y=df_torque["steering_wheel_torque"],
                               name="Torque (lb-ft)", line=dict(color="#9B59B6", width=1))
                )
                fig_torque.update_layout(title="Steering Wheel Torque", height=400,
                                          xaxis_title="Time (minutes)", yaxis_title="Torque (lb-ft)",
                                          margin=dict(t=40, b=40))

            st.plotly_chart(fig_torque, use_container_width=True)

    with col2:
        # Steering torque vs speed scatter (power steering load curve)
        if has_steer_torque and "speed_mph" in df.columns:
            df_steer_scatter = df[(df["steering_wheel_torque"].notna()) & (df["speed_mph"].notna())].copy()
            df_steer_scatter["abs_torque"] = df_steer_scatter["steering_wheel_torque"].abs()

            if not df_steer_scatter.empty:
                fig_steer_load = px.scatter(
                    df_steer_scatter, x="speed_mph", y="abs_torque",
                    color="motor_actual_current" if has_eps_current and "motor_actual_current" in df_steer_scatter.columns else None,
                    color_continuous_scale="Viridis",
                    labels={"speed_mph": "Vehicle Speed (mph)", "abs_torque": "|Steering Torque| (lb-ft)",
                            "motor_actual_current": "EPS Current (A)"},
                    title="Steering Load vs Speed",
                    opacity=0.3
                )
                fig_steer_load.update_layout(height=400, margin=dict(t=40, b=40))
                st.plotly_chart(fig_steer_load, use_container_width=True)

# ===== ROUTE MAPS =====
st.subheader("🗺️ Route Maps")

gps_points = gps_data.get("points", [])
events = events_data.get("events", [])

if len(df) > 0:
    # Filter to points with valid GPS
    df_gps = df[(df['latitude'].notna()) & (df['longitude'].notna()) & (df['latitude'] != 0)].copy()

    if not df_gps.empty:
        # Calculate center
        center_lat = df_gps['latitude'].mean()
        center_lng = df_gps['longitude'].mean()

        map_tab1, map_tab2 = st.tabs(["Speed Map", "Fuel Consumption Map"])

        with map_tab1:
            # Create speed map
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

            st_folium(m, width=None, height=600, use_container_width=True, returned_objects=[])

        with map_tab2:
            # Fuel consumption heatmap
            has_fuel_rate = "fuel_rate_gal_hr" in df_gps.columns and df_gps["fuel_rate_gal_hr"].notna().any()

            if has_fuel_rate:
                m_fuel = folium.Map(location=[center_lat, center_lng], zoom_start=12)

                df_fuel_gps = df_gps[df_gps["fuel_rate_gal_hr"].notna()].copy()

                if not df_fuel_gps.empty:
                    # Normalize fuel rate for coloring
                    fuel_min = df_fuel_gps["fuel_rate_gal_hr"].quantile(0.05)
                    fuel_max = df_fuel_gps["fuel_rate_gal_hr"].quantile(0.95)

                    for i in range(len(df_fuel_gps) - 1):
                        if i % 10 != 0:
                            continue

                        row1 = df_fuel_gps.iloc[i]
                        row2 = df_fuel_gps.iloc[i + 1]

                        fuel_rate = row1.get("fuel_rate_gal_hr", 0) or 0

                        # Color: green (efficient) to red (guzzling)
                        if fuel_max > fuel_min:
                            ratio = min(1, max(0, (fuel_rate - fuel_min) / (fuel_max - fuel_min)))
                        else:
                            ratio = 0.5

                        r = int(255 * ratio)
                        g = int(255 * (1 - ratio))
                        color = f'#{r:02x}{g:02x}00'

                        folium.PolyLine(
                            locations=[[row1['latitude'], row1['longitude']],
                                      [row2['latitude'], row2['longitude']]],
                            color=color,
                            weight=4,
                            opacity=0.8,
                            tooltip=f"{fuel_rate:.2f} gal/hr"
                        ).add_to(m_fuel)

                    # Start/end markers
                    folium.Marker(
                        [df_fuel_gps.iloc[0]['latitude'], df_fuel_gps.iloc[0]['longitude']],
                        popup="Start", icon=folium.Icon(color="green", icon="play")
                    ).add_to(m_fuel)
                    folium.Marker(
                        [df_fuel_gps.iloc[-1]['latitude'], df_fuel_gps.iloc[-1]['longitude']],
                        popup="End", icon=folium.Icon(color="red", icon="stop")
                    ).add_to(m_fuel)

                    # Legend
                    fuel_legend_html = f'''
                    <div style="position: fixed;
                                bottom: 50px; right: 50px; width: 200px; height: 120px;
                                background-color: white; border:2px solid grey; z-index:9999;
                                font-size:14px; padding: 10px">
                    <p style="margin:0"><b>Fuel Rate Legend:</b></p>
                    <p style="margin:5px 0"><span style="color:#00ff00">━━━</span> Low ({fuel_min:.2f} gal/hr)</p>
                    <p style="margin:5px 0"><span style="color:#ffff00">━━━</span> Medium</p>
                    <p style="margin:5px 0"><span style="color:#ff0000">━━━</span> High ({fuel_max:.2f} gal/hr)</p>
                    </div>
                    '''
                    m_fuel.get_root().html.add_child(folium.Element(fuel_legend_html))

                    st_folium(m_fuel, width=None, height=600, use_container_width=True, returned_objects=[])
            else:
                st.info("No fuel rate data available for consumption map.")
    else:
        st.info("No GPS data with valid coordinates available for route visualization.")
else:
    st.info("No GPS data available for route visualization.")

# Raw data section
with st.expander("📊 View Raw Data"):
    st.dataframe(df, height=400)
