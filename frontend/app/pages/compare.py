import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Input, Output, dash_table
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from app.api_client import api_client

dash.register_page(__name__, path="/compare", title="Compare - OBD2")

COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

layout = dbc.Container([
    html.H1("Trip Comparison", className="mb-3"),

    html.Div(id="compare-trip-selector"),
    dcc.Dropdown(id="compare-trip-select", multi=True, placeholder="Select 2-5 trips to compare...",
                 className="mb-4"),

    dcc.Loading(
        html.Div(id="compare-content"),
        type="default",
    ),
], fluid=True)


@callback(
    Output("compare-trip-select", "options"),
    Input("compare-trip-select", "id"),
)
def load_trip_options(_):
    try:
        trips = api_client.list_trips()
        return [{"label": t["name"], "value": t["id"]} for t in trips]
    except Exception:
        return []


@callback(
    Output("compare-content", "children"),
    Input("compare-trip-select", "value"),
)
def update_comparison(selected_ids):
    if not selected_ids or len(selected_ids) < 2:
        return dbc.Alert("Select at least 2 trips to compare.", color="info")

    if len(selected_ids) > 5:
        return dbc.Alert("Please select at most 5 trips.", color="warning")

    trip_data = {}
    telemetry_data = {}

    for trip_id in selected_ids:
        try:
            trip_data[trip_id] = api_client.get_trip(trip_id)
            telemetry_data[trip_id] = api_client.get_telemetry(trip_id, limit=50000)
        except Exception as e:
            return dbc.Alert(f"Error fetching data: {str(e)}", color="danger")

    # Comparison table
    comparison_rows = []
    for trip_id, trip in trip_data.items():
        start = datetime.fromisoformat(trip["start_time"].replace("Z", "+00:00"))
        comparison_rows.append({
            "Trip": trip["name"],
            "Date": start.strftime("%Y-%m-%d"),
            "Duration (min)": f"{trip['duration_seconds'] / 60:.1f}",
            "Max Speed (mph)": f"{trip.get('max_speed_mph', 0):.1f}" if trip.get("max_speed_mph") else "N/A",
            "Avg Speed (mph)": f"{trip.get('avg_speed_mph', 0):.1f}" if trip.get("avg_speed_mph") else "N/A",
            "Data Points": f"{trip.get('row_count', 0):,}",
        })

    comparison_df = pd.DataFrame(comparison_rows)

    # Speed overlay chart
    fig_speed = go.Figure()
    for i, (trip_id, data) in enumerate(telemetry_data.items()):
        df = pd.DataFrame(data["data"])
        trip_name = trip_data[trip_id]["name"]
        fig_speed.add_trace(go.Scatter(
            x=df["elapsed_seconds"], y=df["speed_mph"],
            name=trip_name, mode="lines",
            line=dict(color=COLORS[i % len(COLORS)]),
        ))

    fig_speed.update_layout(
        height=500, xaxis_title="Time (seconds)", yaxis_title="Speed (MPH)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified", template="plotly_dark",
    )

    # Bar charts
    max_speeds = [{"Trip": trip_data[tid]["name"], "val": trip_data[tid].get("max_speed_mph", 0) or 0}
                  for tid in selected_ids]
    avg_speeds = [{"Trip": trip_data[tid]["name"], "val": trip_data[tid].get("avg_speed_mph", 0) or 0}
                  for tid in selected_ids]
    durations = [{"Trip": trip_data[tid]["name"], "val": trip_data[tid]["duration_seconds"] / 60}
                 for tid in selected_ids]

    fig_max = go.Figure(data=[go.Bar(
        x=[d["Trip"] for d in max_speeds], y=[d["val"] for d in max_speeds],
        marker_color=COLORS[:len(max_speeds)],
    )])
    fig_max.update_layout(title="Max Speed Comparison", yaxis_title="Speed (MPH)", height=350, template="plotly_dark")

    fig_avg = go.Figure(data=[go.Bar(
        x=[d["Trip"] for d in avg_speeds], y=[d["val"] for d in avg_speeds],
        marker_color=COLORS[:len(avg_speeds)],
    )])
    fig_avg.update_layout(title="Average Speed Comparison", yaxis_title="Speed (MPH)", height=350, template="plotly_dark")

    fig_dur = go.Figure(data=[go.Bar(
        x=[d["Trip"] for d in durations], y=[d["val"] for d in durations],
        marker_color=COLORS[:len(durations)],
    )])
    fig_dur.update_layout(title="Trip Duration Comparison", yaxis_title="Duration (minutes)", height=350,
                          template="plotly_dark")

    return html.Div([
        html.H3("Trip Metrics Comparison", className="mt-3"),
        dash_table.DataTable(
            data=comparison_df.to_dict("records"),
            columns=[{"name": c, "id": c} for c in comparison_df.columns],
            style_header={"backgroundColor": "#303030", "color": "white", "fontWeight": "bold"},
            style_cell={"backgroundColor": "#222", "color": "white", "textAlign": "center"},
            style_table={"overflowX": "auto"},
        ),

        html.H3("Speed Comparison", className="mt-4"),
        dcc.Graph(figure=fig_speed),

        html.H3("Statistics Summary", className="mt-4"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=fig_max), md=6),
            dbc.Col(dcc.Graph(figure=fig_avg), md=6),
        ]),
        dcc.Graph(figure=fig_dur),
    ])
