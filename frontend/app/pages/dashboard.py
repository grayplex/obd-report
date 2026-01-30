import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Input, Output, clientside_callback
import dash_leaflet as dl
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime

from app.api_client import api_client
from app.components.metric_card import metric_card

dash.register_page(__name__, path="/dashboard", title="Dashboard - OBD2")

# Dark template for charts - matches dark UI theme
CHART_TEMPLATE = "plotly_dark"

layout = dbc.Container([
    dcc.Location(id="dashboard-url", refresh=False),
    html.Div([
        html.H1("Trip Dashboard", className="d-inline-block"),
        dbc.Button("Print Report", id="print-button", color="secondary",
                    outline=True, size="sm", className="ms-3 no-print",
                    style={"verticalAlign": "middle"}),
    ], className="mb-3"),

    html.Div(id="dashboard-trip-selector", className="no-print mb-3"),

    dcc.Loading(
        html.Div(id="dashboard-content"),
        type="default",
    ),
], fluid=True)


# Print button clientside callback
clientside_callback(
    "function(n) { if (n) { window.print(); } return ''; }",
    Output("print-button", "title"),
    Input("print-button", "n_clicks"),
    prevent_initial_call=True,
)


@callback(
    Output("dashboard-trip-selector", "children"),
    Input("dashboard-url", "search"),
)
def render_trip_selector(search):
    try:
        trips = api_client.list_trips()
    except Exception:
        trips = []

    if not trips:
        return dbc.Alert("No trips found. Upload a CSV file to get started.", color="info")

    options = [{"label": t["name"], "value": t["id"]} for t in trips]

    # Check URL for trip_id parameter
    default_value = trips[0]["id"]
    if search:
        params = dict(p.split("=") for p in search.lstrip("?").split("&") if "=" in p)
        if "trip_id" in params and params["trip_id"] in [t["id"] for t in trips]:
            default_value = params["trip_id"]

    return dcc.Dropdown(
        id="dashboard-trip-dropdown",
        options=options,
        value=default_value,
        clearable=False,
    )


@callback(
    Output("dashboard-content", "children"),
    Input("dashboard-trip-dropdown", "value"),
    prevent_initial_call=True,
)
def update_dashboard(trip_id):
    if not trip_id:
        return dbc.Alert("Select a trip.", color="info")

    try:
        trip = api_client.get_trip(trip_id)
        summary = api_client.get_trip_summary(trip_id)
        advanced = api_client.get_advanced_analytics(trip_id)
        telemetry = api_client.get_telemetry(trip_id, limit=50000)
        gps_data = api_client.get_gps_points(trip_id, downsample=1)
        events_data = api_client.get_trip_events(trip_id)
    except Exception as e:
        return dbc.Alert(f"Error fetching data: {str(e)}", color="danger")

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

    # Convert telemetry to DataFrame
    df = pd.DataFrame(telemetry["data"])
    if df.empty:
        return dbc.Alert("No telemetry data available for this trip.", color="warning")

    if "sensors" in df.columns:
        sensors_df = pd.json_normalize(df["sensors"])
        df = pd.concat([df.drop("sensors", axis=1), sensors_df], axis=1)

    sections = []

    # ===== TRIP OVERVIEW =====
    start = datetime.fromisoformat(trip_info["start_time"].replace("Z", "+00:00"))
    duration_min = trip_info.get("duration_seconds", 0) / 60
    distance = distance_info.get("total_miles")
    avg_speed = distance_info.get("avg_speed_mph")
    max_speed = distance_info.get("max_speed_mph")
    stops = driving_behavior.get("stop_count")

    sections.append(html.Div([
        html.H3("Trip Overview"),
        dbc.Row([
            dbc.Col(metric_card("Duration", f"{duration_min:.1f} min"), md=2),
            dbc.Col(metric_card("Distance", f"{distance:.2f} mi" if distance else "N/A"), md=2),
            dbc.Col(metric_card("Avg Speed", f"{avg_speed:.1f} mph" if avg_speed else "N/A"), md=2),
            dbc.Col(metric_card("Max Speed", f"{max_speed:.1f} mph" if max_speed else "N/A"), md=2),
            dbc.Col(metric_card("Stops", f"{stops}" if stops is not None else "N/A"), md=2),
            dbc.Col(metric_card("Date", start.strftime("%Y-%m-%d")), md=2),
        ], className="mb-4"),
    ], className="chart-section"))

    # ===== SPEED RANGE BREAKDOWN =====
    if speed_ranges:
        labels = []
        values = []
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']

        for range_name, data in speed_ranges.items():
            labels.append(f"{range_name.title()}\n{data['percentage']:.1f}%")
            values.append(data['time'])

        fig_pie = go.Figure(data=[go.Pie(
            labels=labels, values=values,
            marker=dict(colors=colors), hole=0.3
        )])
        fig_pie.update_layout(title="Time by Speed Range", height=350, margin=dict(t=40, b=0),
                              template=CHART_TEMPLATE)

        range_data = []
        for range_name, data in speed_ranges.items():
            range_data.append({
                "Range": f"{range_name.title()} ({data['min']}-{data['max']} mph)",
                "Time (min)": data['time'] / 60,
                "Distance (mi)": data['distance'],
            })
        range_df = pd.DataFrame(range_data)

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=range_df["Range"], y=range_df["Time (min)"],
                                 name="Time (minutes)", marker_color='lightblue', yaxis='y'))
        fig_bar.add_trace(go.Bar(x=range_df["Range"], y=range_df["Distance (mi)"],
                                 name="Distance (miles)", marker_color='lightgreen', yaxis='y2'))
        fig_bar.update_layout(
            title="Speed Range Breakdown",
            yaxis=dict(title="Time (minutes)"),
            yaxis2=dict(title="Distance (miles)", overlaying='y', side='right'),
            barmode='group', height=350, margin=dict(t=40, b=0), template=CHART_TEMPLATE,
        )

        sections.append(html.Div([
            html.H3("Speed Range Analysis"),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=fig_pie), md=4),
                dbc.Col(dcc.Graph(figure=fig_bar), md=8),
            ]),
        ], className="chart-section"))

    # ===== FUEL & EFFICIENCY =====
    avg_mpg = fuel_economy.get("avg_mpg")
    total_fuel = fuel_economy.get("total_fuel_gal")
    efficiency_score = fuel_economy.get("efficiency_score")
    optimal_cruising = fuel_insights.get('optimal_cruising', {})
    optimal_mpg = optimal_cruising.get('avg_mpg', 0)
    idle_pct = time_breakdown.get("idle_percentage")

    sections.append(html.Div([
        html.H3("Fuel & Efficiency"),
        dbc.Row([
            dbc.Col(metric_card("Avg MPG", f"{avg_mpg:.1f}" if avg_mpg else "N/A"), md=2),
            dbc.Col(metric_card("Fuel Used", f"{total_fuel:.2f} gal" if total_fuel else "N/A"), md=2),
            dbc.Col(metric_card("Efficiency Score", f"{efficiency_score:.0f}%" if efficiency_score else "N/A"), md=2),
            dbc.Col(metric_card("Peak Efficiency MPG",
                                f"{optimal_mpg:.1f}" if optimal_mpg else "N/A",
                                delta="Optimal cruising" if optimal_mpg else None), md=3),
            dbc.Col(metric_card("Idle Time",
                                f"{idle_pct:.1f}%" if idle_pct is not None else "N/A",
                                delta=f"-{idle_pct:.1f}%" if idle_pct is not None else None,
                                delta_color="inverse"), md=3),
        ], className="mb-4"),
    ], className="chart-section"))

    # ===== COLD START IMPACT =====
    if cold_start and cold_start.get("cold_samples", 0) > 0 and cold_start.get("warm_samples", 0) > 0:
        penalty = cold_start.get('mpg_penalty_pct', 0)
        cold_temp = cold_start.get('cold_start_temp_f')

        cold_metrics = dbc.Row([
            dbc.Col(metric_card("Cold MPG (first 5 min)", f"{cold_start['cold_avg_mpg']:.1f}"), md=3),
            dbc.Col(metric_card("Warm MPG (after 5 min)", f"{cold_start['warm_avg_mpg']:.1f}"), md=3),
            dbc.Col(metric_card("Cold Start Penalty", f"{penalty:.1f}%",
                                delta=f"-{penalty:.1f}% MPG", delta_color="inverse"), md=3),
            dbc.Col(metric_card("Starting Coolant Temp",
                                f"{cold_temp:.0f} F" if cold_temp else "N/A"), md=3),
        ], className="mb-3")

        # Cold start chart
        df_cold = df[df["elapsed_seconds"] <= 600].copy()
        has_coolant = "engine_coolant_temp_f" in df_cold.columns and df_cold["engine_coolant_temp_f"].notna().any()
        has_mpg = "instant_mpg" in df_cold.columns and df_cold["instant_mpg"].notna().any()

        cold_chart = None
        if has_coolant or has_mpg:
            fig_cold = make_subplots(specs=[[{"secondary_y": True}]])

            if has_coolant:
                df_coolant = df_cold[df_cold["engine_coolant_temp_f"].notna()]
                fig_cold.add_trace(
                    go.Scatter(x=df_coolant["elapsed_seconds"] / 60, y=df_coolant["engine_coolant_temp_f"],
                               name="Coolant Temp (F)", line=dict(color="#FF6B6B", width=2)),
                    secondary_y=False
                )

            if has_mpg:
                df_mpg_cold = df_cold[(df_cold["instant_mpg"].notna()) & (df_cold["instant_mpg"] < 100) & (df_cold["speed_mph"] > 5)]
                if not df_mpg_cold.empty:
                    df_mpg_cold = df_mpg_cold.copy()
                    df_mpg_cold["mpg_smooth"] = df_mpg_cold["instant_mpg"].rolling(window=20, min_periods=1).mean()
                    fig_cold.add_trace(
                        go.Scatter(x=df_mpg_cold["elapsed_seconds"] / 60, y=df_mpg_cold["mpg_smooth"],
                                   name="MPG (smoothed)", line=dict(color="#4ECDC4", width=2)),
                        secondary_y=True
                    )

            fig_cold.add_vline(x=5, line_dash="dash", line_color="gray", annotation_text="Warmup threshold")
            fig_cold.update_layout(title="Cold Start: Coolant Temperature & Fuel Economy (First 10 Minutes)",
                                   height=350, margin=dict(t=40, b=40), template=CHART_TEMPLATE)
            fig_cold.update_xaxes(title_text="Time (minutes)")
            fig_cold.update_yaxes(title_text="Coolant Temp (F)", secondary_y=False)
            fig_cold.update_yaxes(title_text="MPG", secondary_y=True)
            cold_chart = dcc.Graph(figure=fig_cold)

        sections.append(html.Div([
            html.H3("Cold Start Impact"),
            cold_metrics,
            cold_chart if cold_chart else "",
        ], className="chart-section"))

    # ===== ENGINE LOAD EFFICIENCY =====
    has_load = "calculated_load_pct" in df.columns and df["calculated_load_pct"].notna().any()
    has_mpg_data = "instant_mpg" in df.columns and df["instant_mpg"].notna().any()

    if has_load and has_mpg_data:
        df_eff = df[(df["calculated_load_pct"].notna()) & (df["instant_mpg"].notna()) &
                    (df["instant_mpg"] > 0) & (df["instant_mpg"] < 100) &
                    (df["speed_mph"] > 5)].copy()

        if not df_eff.empty:
            fig_load = px.scatter(
                df_eff, x="calculated_load_pct", y="instant_mpg",
                color="speed_mph", color_continuous_scale="Viridis",
                labels={"calculated_load_pct": "Engine Load (%)", "instant_mpg": "Instant MPG",
                        "speed_mph": "Speed (mph)"},
                title="Engine Load vs MPG (colored by speed)", opacity=0.4
            )
            fig_load.update_layout(height=400, margin=dict(t=40, b=40), template=CHART_TEMPLATE)

            right_chart = None
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
                fig_alt.update_layout(title="Altitude Profile & Fuel Economy", height=400,
                                      margin=dict(t=40, b=40), template=CHART_TEMPLATE)
                fig_alt.update_xaxes(title_text="Time (minutes)")
                fig_alt.update_yaxes(title_text="Altitude (ft)", secondary_y=False)
                fig_alt.update_yaxes(title_text="MPG", secondary_y=True)
                right_chart = dcc.Graph(figure=fig_alt)
            else:
                fig_hist = px.histogram(df_eff, x="calculated_load_pct", nbins=30,
                                        title="Engine Load Distribution",
                                        labels={"calculated_load_pct": "Engine Load (%)"})
                fig_hist.update_layout(height=400, margin=dict(t=40, b=40), template=CHART_TEMPLATE)
                right_chart = dcc.Graph(figure=fig_hist)

            sections.append(html.Div([
                html.H3("Engine Load vs Fuel Efficiency"),
                dbc.Row([
                    dbc.Col(dcc.Graph(figure=fig_load), md=6),
                    dbc.Col(right_chart, md=6),
                ]),
            ], className="chart-section"))

    # ===== DRIVING BEHAVIOR =====
    driving_score = driving_behavior.get("driving_score")
    event_counts = driving_behavior.get("event_counts", {})
    hard_events = event_counts.get("hard_brake", 0) + event_counts.get("hard_accel", 0)

    behavior_metrics = dbc.Row([
        dbc.Col(metric_card("Driving Score",
                            f"{driving_score:.0f}/100" if driving_score is not None else "N/A",
                            delta="Perfect!" if driving_score == 100 else None), md=2),
        dbc.Col(metric_card("Hard Events", f"{hard_events}"), md=2),
        dbc.Col(metric_card("Aggressiveness",
                            f"{throttle_patterns.get('aggressiveness_score', 0):.0f}/100" if throttle_patterns else "N/A",
                            delta="Gentle" if throttle_patterns and throttle_patterns.get('aggressiveness_score', 100) < 30 else (
                                "Aggressive" if throttle_patterns else None),
                            delta_color="inverse" if throttle_patterns and throttle_patterns.get('aggressiveness_score', 100) < 30 else "normal"),
                md=3),
        dbc.Col(metric_card("Avg Throttle",
                            f"{throttle_patterns.get('avg_throttle', 0):.1f}%" if throttle_patterns else "N/A"), md=2),
        dbc.Col(metric_card("Gentle Driving",
                            f"{throttle_patterns.get('distribution', {}).get('gentle_pct', 0):.1f}%" if throttle_patterns else "N/A",
                            delta="Good" if throttle_patterns else None), md=3),
    ], className="mb-3")

    behavior_charts = []
    if throttle_patterns:
        dist = throttle_patterns.get('distribution', {})
        dist_df = pd.DataFrame({
            "Category": ["Gentle (0-30%)", "Moderate (30-60%)", "Aggressive (60-80%)", "Very Aggressive (80-100%)"],
            "Percentage": [dist.get('gentle_pct', 0), dist.get('moderate_pct', 0),
                          dist.get('aggressive_pct', 0), dist.get('very_aggressive_pct', 0)],
            "Color": ['#2ECC71', '#3498DB', '#F39C12', '#E74C3C']
        })
        fig_throttle_dist = go.Figure(data=[
            go.Bar(x=dist_df["Category"], y=dist_df["Percentage"], marker_color=dist_df["Color"])
        ])
        fig_throttle_dist.update_layout(title="Throttle Input Distribution", yaxis_title="Percentage of Time (%)",
                                        height=400, margin=dict(t=40, b=60), template=CHART_TEMPLATE)
        behavior_charts.append(dbc.Col(dcc.Graph(figure=fig_throttle_dist), md=6))

    # Throttle vs Acceleration scatter
    has_pedal = "accelerator_pedal_position_pct" in df.columns and df["accelerator_pedal_position_pct"].notna().any()
    has_accel = "acceleration_g" in df.columns and df["acceleration_g"].notna().any()

    if has_pedal and has_accel:
        df_ta = df[(df["accelerator_pedal_position_pct"].notna()) &
                   (df["acceleration_g"].notna()) & (df["speed_mph"] > 5)].copy()
        if not df_ta.empty:
            fig_ta = px.scatter(
                df_ta, x="accelerator_pedal_position_pct", y="acceleration_g",
                color="speed_mph", color_continuous_scale="Plasma",
                labels={"accelerator_pedal_position_pct": "Pedal Position (%)",
                        "acceleration_g": "Acceleration (g)", "speed_mph": "Speed (mph)"},
                title="Pedal Input vs Actual Acceleration", opacity=0.3
            )
            fig_ta.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig_ta.update_layout(height=400, margin=dict(t=40, b=60), template=CHART_TEMPLATE)
            behavior_charts.append(dbc.Col(dcc.Graph(figure=fig_ta), md=6))
    elif not has_pedal and has_accel and "throttle_position_pct" in df.columns:
        df_ta = df[(df["throttle_position_pct"].notna()) &
                   (df["acceleration_g"].notna()) & (df["speed_mph"] > 5)].copy()
        if not df_ta.empty:
            fig_ta = px.scatter(
                df_ta, x="throttle_position_pct", y="acceleration_g",
                color="speed_mph", color_continuous_scale="Plasma",
                labels={"throttle_position_pct": "Throttle Position (%)",
                        "acceleration_g": "Acceleration (g)", "speed_mph": "Speed (mph)"},
                title="Throttle Position vs Actual Acceleration", opacity=0.3
            )
            fig_ta.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
            fig_ta.update_layout(height=400, margin=dict(t=40, b=60), template=CHART_TEMPLATE)
            behavior_charts.append(dbc.Col(dcc.Graph(figure=fig_ta), md=6))

    sections.append(html.Div([
        html.H3("Driving Behavior & Throttle Analysis"),
        behavior_metrics,
        dbc.Row(behavior_charts) if behavior_charts else "",
    ], className="chart-section"))

    # ===== CRUISE CONTROL =====
    if cruise_stats and cruise_stats.get('session_count', 0) > 0:
        total_cruise = cruise_stats.get('total_cruise_time', 0)
        session_count = cruise_stats.get('session_count', 0)
        avg_duration = cruise_stats.get('avg_session_duration', 0)

        cruise_chart = None
        sessions = cruise_stats.get('sessions', [])
        if sessions:
            fig_timeline = go.Figure()
            for i, session in enumerate(sessions):
                duration = session['duration']
                s_avg_speed = session.get('avg_speed', 0)
                fig_timeline.add_trace(go.Bar(
                    name=f"Session {i+1}", x=[duration], y=[f"{s_avg_speed:.0f} mph"],
                    orientation='h',
                    marker=dict(color=f'rgb({50 + i*20}, {100 + i*15}, {200 - i*10})'),
                    text=f"{duration/60:.1f} min", textposition='inside',
                    hovertemplate=f"Speed: {s_avg_speed:.1f} mph<br>Duration: {duration/60:.1f} min<extra></extra>"
                ))
            fig_timeline.update_layout(title="Cruise Control Sessions Timeline",
                                       xaxis_title="Duration (seconds)", yaxis_title="Average Speed",
                                       barmode='stack', showlegend=False, height=300,
                                       margin=dict(t=40, b=60), template=CHART_TEMPLATE)
            cruise_chart = dcc.Graph(figure=fig_timeline)

        sections.append(html.Div([
            html.H3("Cruise Control Usage"),
            dbc.Row([
                dbc.Col(metric_card("Total Cruise Time", f"{total_cruise / 60:.1f} min"), md=4),
                dbc.Col(metric_card("Cruise Sessions", f"{session_count}"), md=4),
                dbc.Col(metric_card("Avg Session Duration", f"{avg_duration / 60:.1f} min"), md=4),
            ], className="mb-3"),
            cruise_chart if cruise_chart else "",
        ], className="chart-section"))

    # ===== PERFORMANCE CHARTS =====
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("Speed Over Time", "Engine RPM", "Throttle Position", "Fuel Economy"),
    )

    if "speed_mph" in df.columns:
        fig.add_trace(go.Scatter(x=df["elapsed_seconds"], y=df["speed_mph"],
                                 name="Speed", line=dict(color="blue")), row=1, col=1)
    if "engine_rpm" in df.columns:
        fig.add_trace(go.Scatter(x=df["elapsed_seconds"], y=df["engine_rpm"],
                                 name="RPM", line=dict(color="red")), row=1, col=2)
    if "throttle_position_pct" in df.columns:
        fig.add_trace(go.Scatter(x=df["elapsed_seconds"], y=df["throttle_position_pct"],
                                 name="Throttle", line=dict(color="green")), row=2, col=1)
    if "instant_mpg" in df.columns:
        mpg_filtered = df[df["instant_mpg"] < 100]
        fig.add_trace(go.Scatter(x=mpg_filtered["elapsed_seconds"], y=mpg_filtered["instant_mpg"],
                                 name="MPG", line=dict(color="purple")), row=2, col=2)

    fig.update_xaxes(title_text="Time (seconds)", row=1, col=1)
    fig.update_xaxes(title_text="Time (seconds)", row=1, col=2)
    fig.update_xaxes(title_text="Time (seconds)", row=2, col=1)
    fig.update_xaxes(title_text="Time (seconds)", row=2, col=2)
    fig.update_yaxes(title_text="MPH", row=1, col=1)
    fig.update_yaxes(title_text="RPM", row=1, col=2)
    fig.update_yaxes(title_text="%", row=2, col=1)
    fig.update_yaxes(title_text="MPG", row=2, col=2)
    fig.update_layout(height=700, showlegend=False, template=CHART_TEMPLATE)

    sections.append(html.Div([
        html.H3("Speed & Performance", className="section-break"),
        dcc.Graph(figure=fig),
    ], className="chart-section"))

    # ===== CVT RATIO ANALYSIS =====
    has_rpm = "engine_rpm" in df.columns and df["engine_rpm"].notna().any()
    has_speed = "speed_mph" in df.columns and df["speed_mph"].notna().any()

    if has_rpm and has_speed:
        df_cvt = df[(df["engine_rpm"].notna()) & (df["speed_mph"] > 5) & (df["engine_rpm"] > 500)].copy()
        if not df_cvt.empty:
            fig_cvt = px.scatter(
                df_cvt, x="speed_mph", y="engine_rpm",
                color="throttle_position_pct" if "throttle_position_pct" in df_cvt.columns else None,
                color_continuous_scale="YlOrRd",
                labels={"speed_mph": "Vehicle Speed (mph)", "engine_rpm": "Engine RPM",
                        "throttle_position_pct": "Throttle (%)"},
                title="CVT Ratio Map: RPM vs Speed", opacity=0.3
            )
            fig_cvt.update_layout(height=450, margin=dict(t=40, b=40), template=CHART_TEMPLATE)

            right_cvt = None
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
                                   name="NIN (Input)", line=dict(color="#E74C3C")), row=1, col=1)
                    fig_cvt_ratio.add_trace(
                        go.Scatter(x=df_cvt_int["elapsed_seconds"] / 60, y=df_cvt_int["speed_of_nout"],
                                   name="NOUT (Output)", line=dict(color="#3498DB")), row=1, col=1)
                    fig_cvt_ratio.add_trace(
                        go.Scatter(x=df_cvt_int["elapsed_seconds"] / 60, y=df_cvt_int["cvt_ratio"],
                                   name="Ratio", line=dict(color="#2ECC71")), row=2, col=1)
                    fig_cvt_ratio.update_layout(height=450, margin=dict(t=40, b=40), template=CHART_TEMPLATE)
                    fig_cvt_ratio.update_xaxes(title_text="Time (minutes)", row=2, col=1)
                    fig_cvt_ratio.update_yaxes(title_text="RPM", row=1, col=1)
                    fig_cvt_ratio.update_yaxes(title_text="Ratio (NIN/NOUT)", row=2, col=1)
                    right_cvt = dcc.Graph(figure=fig_cvt_ratio)
            else:
                df_cvt["rpm_per_mph"] = df_cvt["engine_rpm"] / df_cvt["speed_mph"]
                fig_eff_zone = px.histogram(df_cvt, x="rpm_per_mph", nbins=50,
                                            title="RPM/MPH Distribution (lower = more efficient)",
                                            labels={"rpm_per_mph": "RPM per MPH"})
                fig_eff_zone.update_layout(height=450, margin=dict(t=40, b=40), template=CHART_TEMPLATE)
                right_cvt = dcc.Graph(figure=fig_eff_zone)

            sections.append(html.Div([
                html.H3("CVT Ratio Analysis"),
                dbc.Row([
                    dbc.Col(dcc.Graph(figure=fig_cvt), md=6),
                    dbc.Col(right_cvt if right_cvt else "", md=6),
                ]),
            ], className="chart-section"))

    # ===== ENGINE & CVT HEALTH =====
    has_at_oil = "a_t_oil_temperature_1" in df.columns and df["a_t_oil_temperature_1"].notna().any()
    _vvt_col = "vvt_ex_chg_angle_bank1" if "vvt_ex_chg_angle_bank1" in df.columns else "vvt_ex_chg_angle"
    has_vvt = _vvt_col in df.columns and df[_vvt_col].notna().any()
    has_knock = "knock_feedback_value" in df.columns and df["knock_feedback_value"].notna().any()
    has_fuel_cut = "fuel_cut_condition" in df.columns and df["fuel_cut_condition"].notna().any()
    has_short_ft = "short_ft_b1s1" in df.columns and df["short_ft_b1s1"].notna().any()
    has_long_ft = "long_ft_b1s1" in df.columns and df["long_ft_b1s1"].notna().any()

    if has_at_oil or has_vvt or has_knock or has_fuel_cut or has_short_ft or has_long_ft:
        num_subplots = int(sum([has_at_oil, has_vvt, has_knock or has_fuel_cut, has_short_ft or has_long_ft]))
        if num_subplots > 0:
            titles = []
            if has_at_oil: titles.append("A/T Oil Temperature")
            if has_vvt: titles.append("VVT Exhaust Cam Angle")
            if has_knock or has_fuel_cut: titles.append("Knock & Fuel Cut")
            if has_short_ft or has_long_ft: titles.append("Fuel Trims (B1S1)")

            fig_toyota = make_subplots(rows=num_subplots, cols=1, subplot_titles=titles,
                                        shared_xaxes=True, vertical_spacing=0.08)
            row_idx = 1

            if has_at_oil:
                df_oil = df[df["a_t_oil_temperature_1"].notna()]
                fig_toyota.add_trace(
                    go.Scatter(x=df_oil["elapsed_seconds"] / 60, y=df_oil["a_t_oil_temperature_1"],
                               name="A/T Oil Temp (F)", line=dict(color="#E74C3C")), row=row_idx, col=1)
                fig_toyota.update_yaxes(title_text="F", row=row_idx, col=1)
                row_idx += 1

            if has_vvt:
                df_vvt = df[df[_vvt_col].notna()]
                fig_toyota.add_trace(
                    go.Scatter(x=df_vvt["elapsed_seconds"] / 60, y=df_vvt[_vvt_col],
                               name="VVT Angle (deg)", line=dict(color="#9B59B6")), row=row_idx, col=1)
                fig_toyota.update_yaxes(title_text="Degrees", row=row_idx, col=1)
                row_idx += 1

            if has_knock or has_fuel_cut:
                if has_knock:
                    df_knock = df[df["knock_feedback_value"].notna()]
                    fig_toyota.add_trace(
                        go.Scatter(x=df_knock["elapsed_seconds"] / 60, y=df_knock["knock_feedback_value"],
                                   name="Knock Feedback (deg)", line=dict(color="#F39C12")), row=row_idx, col=1)
                if has_fuel_cut:
                    df_fc = df[df["fuel_cut_condition"].notna()]
                    fig_toyota.add_trace(
                        go.Scatter(x=df_fc["elapsed_seconds"] / 60, y=df_fc["fuel_cut_condition"],
                                   name="Fuel Cut", line=dict(color="#1ABC9C"), opacity=0.7), row=row_idx, col=1)
                fig_toyota.update_yaxes(title_text="Value", row=row_idx, col=1)
                row_idx += 1

            if has_short_ft or has_long_ft:
                if has_short_ft:
                    df_sft = df[df["short_ft_b1s1"].notna()]
                    fig_toyota.add_trace(
                        go.Scatter(x=df_sft["elapsed_seconds"] / 60, y=df_sft["short_ft_b1s1"],
                                   name="Short FT B1S1 (%)", line=dict(color="#3498DB")), row=row_idx, col=1)
                if has_long_ft:
                    df_lft = df[df["long_ft_b1s1"].notna()]
                    fig_toyota.add_trace(
                        go.Scatter(x=df_lft["elapsed_seconds"] / 60, y=df_lft["long_ft_b1s1"],
                                   name="Long FT B1S1 (%)", line=dict(color="#E67E22")), row=row_idx, col=1)
                fig_toyota.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4, row=row_idx, col=1)
                fig_toyota.update_yaxes(title_text="%", row=row_idx, col=1)

            fig_toyota.update_xaxes(title_text="Time (minutes)", row=num_subplots, col=1)
            fig_toyota.update_layout(height=250 * num_subplots, margin=dict(t=40, b=40), template=CHART_TEMPLATE)

            sections.append(html.Div([
                html.H3("Engine & CVT Health (Toyota ECT)"),
                dcc.Graph(figure=fig_toyota),
            ], className="chart-section"))

    # ===== THROTTLE HEAT MAP =====
    if "throttle_position_pct" in df.columns:
        df_throttle = df[df["throttle_position_pct"].notna()].copy()
        if len(df_throttle) > 0:
            time_bins = 50
            throttle_bins = 20
            df_throttle["time_bin"] = pd.cut(df_throttle["elapsed_seconds"], bins=time_bins)
            df_throttle["throttle_bin"] = pd.cut(df_throttle["throttle_position_pct"], bins=throttle_bins)
            heatmap_data = df_throttle.groupby(["time_bin", "throttle_bin"]).size().reset_index(name='count')
            pivot_data = heatmap_data.pivot_table(index='throttle_bin', columns='time_bin',
                                                   values='count', fill_value=0)

            fig_heatmap = go.Figure(data=go.Heatmap(z=pivot_data.values, colorscale='YlOrRd', showscale=True))
            fig_heatmap.update_layout(title="Throttle Position Intensity Over Trip",
                                      xaxis_title="Trip Progress", yaxis_title="Throttle Position (%) ",
                                      height=300, margin=dict(t=40, b=60), template=CHART_TEMPLATE)

            sections.append(html.Div([
                html.H3("Throttle Position Heat Map"),
                dcc.Graph(figure=fig_heatmap),
            ], className="chart-section"))

    # ===== VEHICLE DYNAMICS =====
    has_lateral_g = "lateral_g" in df.columns and df["lateral_g"].notna().any()
    has_fwd_g = "forward_and_rearward_g" in df.columns and df["forward_and_rearward_g"].notna().any()
    has_yaw = "yaw_rate_sensor" in df.columns and df["yaw_rate_sensor"].notna().any()
    has_steering = "steering_angle_sensor" in df.columns and df["steering_angle_sensor"].notna().any()

    if has_lateral_g or has_fwd_g or has_yaw:
        dynamics_cols = []

        if has_lateral_g and has_fwd_g:
            df_g = df[(df["lateral_g"].notna()) & (df["forward_and_rearward_g"].notna())].copy()
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
                    title="G-Force Friction Circle", opacity=0.3
                )
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
                                           yaxis=dict(scaleanchor="x", scaleratio=1), template=CHART_TEMPLATE)
                dynamics_cols.append(dbc.Col(dcc.Graph(figure=fig_friction), md=6))

        # Vehicle stability traces
        stability_traces = int(sum([has_yaw, has_steering, has_lateral_g]))
        if stability_traces >= 2:
            stab_titles = [t for t, h in [("Yaw Rate", has_yaw), ("Steering Angle", has_steering),
                                            ("Lateral G", has_lateral_g)] if h]
            fig_stab = make_subplots(rows=stability_traces, cols=1, shared_xaxes=True,
                                      vertical_spacing=0.08, subplot_titles=stab_titles)
            s_row = 1

            if has_yaw:
                df_yaw = df[df["yaw_rate_sensor"].notna()]
                fig_stab.add_trace(
                    go.Scatter(x=df_yaw["elapsed_seconds"] / 60, y=df_yaw["yaw_rate_sensor"],
                               name="Yaw Rate (deg/s)", line=dict(color="#E74C3C")), row=s_row, col=1)
                fig_stab.update_yaxes(title_text="deg/s", row=s_row, col=1)
                s_row += 1

            if has_steering:
                df_steer = df[df["steering_angle_sensor"].notna()]
                fig_stab.add_trace(
                    go.Scatter(x=df_steer["elapsed_seconds"] / 60, y=df_steer["steering_angle_sensor"],
                               name="Steering Angle (deg)", line=dict(color="#3498DB")), row=s_row, col=1)
                fig_stab.update_yaxes(title_text="deg", row=s_row, col=1)
                s_row += 1

            if has_lateral_g:
                df_lat = df[df["lateral_g"].notna()].copy()
                df_lat["lateral_g_force"] = df_lat["lateral_g"] / 32.174
                fig_stab.add_trace(
                    go.Scatter(x=df_lat["elapsed_seconds"] / 60, y=df_lat["lateral_g_force"],
                               name="Lateral G", line=dict(color="#2ECC71")), row=s_row, col=1)
                fig_stab.update_yaxes(title_text="g", row=s_row, col=1)

            fig_stab.update_xaxes(title_text="Time (minutes)", row=stability_traces, col=1)
            fig_stab.update_layout(height=150 * stability_traces + 100, margin=dict(t=40, b=40),
                                   template=CHART_TEMPLATE)
            dynamics_cols.append(dbc.Col(dcc.Graph(figure=fig_stab), md=6))

        if dynamics_cols:
            sections.append(html.Div([
                html.H3("Vehicle Dynamics"),
                dbc.Row(dynamics_cols),
            ], className="chart-section"))

    # ===== WHEEL SPEED ANALYSIS =====
    wheel_cols = ["fl_wheel_speed", "fr_wheel_speed", "rl_wheel_speed", "rr_wheel_speed"]
    has_wheels = all(c in df.columns and df[c].notna().any() for c in wheel_cols)

    if has_wheels:
        df_wheels = df[df[wheel_cols[0]].notna()].copy()
        if not df_wheels.empty:
            fig_ws = go.Figure()
            wheel_colors = {"fl_wheel_speed": "#E74C3C", "fr_wheel_speed": "#3498DB",
                            "rl_wheel_speed": "#2ECC71", "rr_wheel_speed": "#F39C12"}
            wheel_labels = {"fl_wheel_speed": "FL", "fr_wheel_speed": "FR",
                            "rl_wheel_speed": "RL", "rr_wheel_speed": "RR"}
            for col_name in wheel_cols:
                fig_ws.add_trace(go.Scatter(
                    x=df_wheels["elapsed_seconds"] / 60, y=df_wheels[col_name],
                    name=wheel_labels[col_name], line=dict(color=wheel_colors[col_name], width=1), opacity=0.7
                ))
            fig_ws.update_layout(title="Individual Wheel Speeds", height=400,
                                  xaxis_title="Time (minutes)", yaxis_title="Speed (mph)",
                                  margin=dict(t=40, b=40), template=CHART_TEMPLATE)

            # Wheel speed differential
            df_wheels["front_avg"] = (df_wheels["fl_wheel_speed"] + df_wheels["fr_wheel_speed"]) / 2
            df_wheels["rear_avg"] = (df_wheels["rl_wheel_speed"] + df_wheels["rr_wheel_speed"]) / 2
            df_wheels["lr_diff"] = df_wheels["fl_wheel_speed"] - df_wheels["fr_wheel_speed"]
            df_wheels["fr_diff"] = df_wheels["front_avg"] - df_wheels["rear_avg"]

            fig_diff = make_subplots(rows=2, cols=1,
                                      subplot_titles=("Front-Rear Speed Difference", "Left-Right Speed Difference (Front)"),
                                      shared_xaxes=True)
            fig_diff.add_trace(go.Scatter(x=df_wheels["elapsed_seconds"] / 60, y=df_wheels["fr_diff"],
                                          name="Front - Rear", line=dict(color="#E74C3C", width=1)), row=1, col=1)
            fig_diff.add_trace(go.Scatter(x=df_wheels["elapsed_seconds"] / 60, y=df_wheels["lr_diff"],
                                          name="FL - FR", line=dict(color="#3498DB", width=1)), row=2, col=1)
            fig_diff.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4, row=1, col=1)
            fig_diff.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4, row=2, col=1)
            fig_diff.update_xaxes(title_text="Time (minutes)", row=2, col=1)
            fig_diff.update_yaxes(title_text="MPH diff", row=1, col=1)
            fig_diff.update_yaxes(title_text="MPH diff", row=2, col=1)
            fig_diff.update_layout(height=400, margin=dict(t=40, b=40), template=CHART_TEMPLATE)

            sections.append(html.Div([
                html.H3("Wheel Speed Analysis", className="section-break"),
                dbc.Row([
                    dbc.Col(dcc.Graph(figure=fig_ws), md=6),
                    dbc.Col(dcc.Graph(figure=fig_diff), md=6),
                ]),
            ], className="chart-section"))

    # ===== TIRE PRESSURE & TEMPERATURE =====
    tire_pressure_cols = [f"id_{i}_tire_inflation_pressure" for i in range(1, 5)]
    tire_temp_cols = [f"id_{i}_temperature_in_tire" for i in range(1, 5)]
    has_tire_pressure = any(c in df.columns and df[c].notna().any() for c in tire_pressure_cols)
    has_tire_temp = any(c in df.columns and df[c].notna().any() for c in tire_temp_cols)

    if has_tire_pressure or has_tire_temp:
        tire_charts = []
        tire_colors = ["#E74C3C", "#3498DB", "#2ECC71", "#F39C12"]
        tire_labels = ["FL", "FR", "RL", "RR"]

        if has_tire_pressure:
            fig_tp = go.Figure()
            for i, (col_name, color, label) in enumerate(zip(tire_pressure_cols, tire_colors, tire_labels)):
                if col_name in df.columns and df[col_name].notna().any():
                    df_tp = df[df[col_name].notna()]
                    fig_tp.add_trace(go.Scatter(x=df_tp["elapsed_seconds"] / 60, y=df_tp[col_name],
                                                name=label, line=dict(color=color, width=2)))
            fig_tp.add_hline(y=32, line_dash="dash", line_color="gray", opacity=0.4,
                             annotation_text="Min recommended (32 psi)")
            fig_tp.update_layout(title="Tire Inflation Pressure", height=350,
                                  xaxis_title="Time (minutes)", yaxis_title="Pressure (psi)",
                                  margin=dict(t=40, b=40), template=CHART_TEMPLATE)
            tire_charts.append(dbc.Col(dcc.Graph(figure=fig_tp), md=6))

        if has_tire_temp:
            fig_tt = go.Figure()
            for i, (col_name, color, label) in enumerate(zip(tire_temp_cols, tire_colors, tire_labels)):
                if col_name in df.columns and df[col_name].notna().any():
                    df_tt = df[df[col_name].notna()]
                    fig_tt.add_trace(go.Scatter(x=df_tt["elapsed_seconds"] / 60, y=df_tt[col_name],
                                                name=label, line=dict(color=color, width=2)))
            fig_tt.update_layout(title="Tire Temperature", height=350,
                                  xaxis_title="Time (minutes)", yaxis_title="Temperature (F)",
                                  margin=dict(t=40, b=40), template=CHART_TEMPLATE)
            tire_charts.append(dbc.Col(dcc.Graph(figure=fig_tt), md=6))

        # Tire pressure summary metrics
        tire_metrics = []
        if has_tire_pressure:
            for i, (col_name, label) in enumerate(zip(tire_pressure_cols, tire_labels)):
                if col_name in df.columns and df[col_name].notna().any():
                    current = df[df[col_name].notna()][col_name].iloc[-1]
                    avg_val = df[df[col_name].notna()][col_name].mean()
                    tire_metrics.append(
                        dbc.Col(metric_card(f"{label} Pressure", f"{current:.1f} psi",
                                            delta=f"avg {avg_val:.1f}" if abs(current - avg_val) > 0.5 else None),
                                md=3)
                    )

        sections.append(html.Div([
            html.H3("Tire Pressure & Temperature"),
            dbc.Row(tire_charts),
            dbc.Row(tire_metrics, className="mt-2") if tire_metrics else "",
        ], className="chart-section"))

    # ===== STEERING & EPS =====
    has_steer_torque = "steering_wheel_torque" in df.columns and df["steering_wheel_torque"].notna().any()
    has_eps_current = "motor_actual_current" in df.columns and df["motor_actual_current"].notna().any()

    if has_steer_torque or has_eps_current:
        steer_charts = []

        if has_steer_torque:
            df_torque = df[df["steering_wheel_torque"].notna()].copy()

            if has_eps_current:
                fig_torque = make_subplots(rows=2, cols=1,
                                            subplot_titles=("Steering Wheel Torque", "EPS Motor Current"),
                                            shared_xaxes=True)
                fig_torque.add_trace(
                    go.Scatter(x=df_torque["elapsed_seconds"] / 60, y=df_torque["steering_wheel_torque"],
                               name="Torque (lb-ft)", line=dict(color="#9B59B6", width=1)), row=1, col=1)
                df_eps = df[df["motor_actual_current"].notna()]
                fig_torque.add_trace(
                    go.Scatter(x=df_eps["elapsed_seconds"] / 60, y=df_eps["motor_actual_current"],
                               name="EPS Current (A)", line=dict(color="#E67E22", width=1)), row=2, col=1)
                fig_torque.update_xaxes(title_text="Time (minutes)", row=2, col=1)
                fig_torque.update_yaxes(title_text="lb-ft", row=1, col=1)
                fig_torque.update_yaxes(title_text="Amps", row=2, col=1)
                fig_torque.update_layout(height=400, margin=dict(t=40, b=40), template=CHART_TEMPLATE)
            else:
                fig_torque = go.Figure()
                fig_torque.add_trace(
                    go.Scatter(x=df_torque["elapsed_seconds"] / 60, y=df_torque["steering_wheel_torque"],
                               name="Torque (lb-ft)", line=dict(color="#9B59B6", width=1)))
                fig_torque.update_layout(title="Steering Wheel Torque", height=400,
                                          xaxis_title="Time (minutes)", yaxis_title="Torque (lb-ft)",
                                          margin=dict(t=40, b=40), template=CHART_TEMPLATE)

            steer_charts.append(dbc.Col(dcc.Graph(figure=fig_torque), md=6))

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
                    title="Steering Load vs Speed", opacity=0.3
                )
                fig_steer_load.update_layout(height=400, margin=dict(t=40, b=40), template=CHART_TEMPLATE)
                steer_charts.append(dbc.Col(dcc.Graph(figure=fig_steer_load), md=6))

        if steer_charts:
            sections.append(html.Div([
                html.H3("Steering & Electric Power Steering"),
                dbc.Row(steer_charts),
            ], className="chart-section"))

    # ===== ROUTE MAPS =====
    df_gps = df[(df['latitude'].notna()) & (df['longitude'].notna()) & (df['latitude'] != 0)].copy()

    if not df_gps.empty:
        center_lat = df_gps['latitude'].mean()
        center_lng = df_gps['longitude'].mean()

        # Speed-colored route using Plotly scatter_mapbox for print compatibility
        df_gps_sampled = df_gps.iloc[::10].copy()  # Downsample for performance

        def speed_color(speed):
            if speed < 20: return "red"
            elif speed < 40: return "orange"
            elif speed < 60: return "yellow"
            else: return "green"

        df_gps_sampled["color"] = df_gps_sampled["speed_mph"].apply(speed_color)

        fig_map = px.scatter_mapbox(
            df_gps_sampled, lat="latitude", lon="longitude",
            color="speed_mph", color_continuous_scale="RdYlGn",
            hover_data={"speed_mph": ":.1f", "latitude": ":.5f", "longitude": ":.5f"},
            title="Route Map (colored by speed)",
            zoom=11,
        )
        fig_map.update_layout(
            mapbox_style="open-street-map",
            mapbox=dict(center=dict(lat=center_lat, lon=center_lng)),
            height=600, margin=dict(t=40, b=0, l=0, r=0), template=CHART_TEMPLATE,
        )

        map_tabs = [dbc.Tab(dcc.Graph(figure=fig_map), label="Speed Map")]

        # Fuel consumption map
        has_fuel_rate = "fuel_rate_gal_hr" in df_gps.columns and df_gps["fuel_rate_gal_hr"].notna().any()
        if has_fuel_rate:
            df_fuel_gps = df_gps[df_gps["fuel_rate_gal_hr"].notna()].iloc[::10].copy()
            if not df_fuel_gps.empty:
                fig_fuel_map = px.scatter_mapbox(
                    df_fuel_gps, lat="latitude", lon="longitude",
                    color="fuel_rate_gal_hr", color_continuous_scale="RdYlGn_r",
                    hover_data={"fuel_rate_gal_hr": ":.2f"},
                    title="Fuel Consumption Map",
                    zoom=11,
                )
                fig_fuel_map.update_layout(
                    mapbox_style="open-street-map",
                    mapbox=dict(center=dict(lat=center_lat, lon=center_lng)),
                    height=600, margin=dict(t=40, b=0, l=0, r=0), template=CHART_TEMPLATE,
                )
                map_tabs.append(dbc.Tab(dcc.Graph(figure=fig_fuel_map), label="Fuel Consumption Map"))

        sections.append(html.Div([
            html.H3("Route Maps", className="section-break"),
            dbc.Tabs(map_tabs),
        ], className="chart-section"))

    # ===== RAW DATA =====
    sections.append(html.Div([
        html.H3("Raw Data", className="no-print"),
        dbc.Accordion([
            dbc.AccordionItem(
                html.Div(
                    dbc.Table.from_dataframe(df.head(100), striped=True, bordered=True, hover=True,
                                             responsive=True, size="sm", color="dark"),
                    style={"maxHeight": "400px", "overflowY": "auto"},
                ),
                title="View Raw Data (first 100 rows)",
            ),
        ], start_collapsed=True, className="no-print"),
    ]))

    return html.Div(sections)
