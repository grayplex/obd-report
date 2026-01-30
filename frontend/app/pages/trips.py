import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Input, Output, ALL, ctx
from datetime import datetime

from app.api_client import api_client

dash.register_page(__name__, path="/trips", title="Trips - OBD2")


def make_trip_cards(trips):
    if not trips:
        return dbc.Alert("No trips found. Upload a CSV file to get started.", color="info")

    cards = [html.H4(f"Found {len(trips)} trip(s)", className="mb-3")]

    for trip in trips:
        start = datetime.fromisoformat(trip["start_time"].replace("Z", "+00:00"))
        duration_min = trip["duration_seconds"] / 60
        max_speed = trip.get("max_speed_mph")
        avg_speed = trip.get("avg_speed_mph")

        card = dbc.Card(
            dbc.CardBody(
                dbc.Row([
                    dbc.Col([
                        html.H5(trip["name"], className="mb-0"),
                        html.Small(start.strftime("%Y-%m-%d %H:%M"), className="text-muted"),
                    ], md=3),
                    dbc.Col([
                        html.P("Duration", className="text-muted mb-0", style={"fontSize": "0.8rem"}),
                        html.Strong(f"{duration_min:.1f} min"),
                    ], md=2, className="text-center"),
                    dbc.Col([
                        html.P("Max Speed", className="text-muted mb-0", style={"fontSize": "0.8rem"}),
                        html.Strong(f"{max_speed:.1f} mph" if max_speed else "N/A"),
                    ], md=2, className="text-center"),
                    dbc.Col([
                        html.P("Avg Speed", className="text-muted mb-0", style={"fontSize": "0.8rem"}),
                        html.Strong(f"{avg_speed:.1f} mph" if avg_speed else "N/A"),
                    ], md=2, className="text-center"),
                    dbc.Col([
                        dcc.Link(
                            dbc.Button("View Dashboard", color="primary", size="sm"),
                            href=f"/dashboard?trip_id={trip['id']}",
                        ),
                        dbc.Button("Delete", id={"type": "delete-trip", "index": trip["id"]},
                                   color="danger", size="sm", outline=True, className="ms-2"),
                    ], md=3, className="text-end d-flex align-items-center justify-content-end"),
                ], align="center"),
            ),
            className="mb-2",
        )
        cards.append(card)

    return html.Div(cards)


layout = dbc.Container([
    html.H1("Trip Browser", className="mb-3"),
    dcc.Loading(
        html.Div(id="trips-list"),
        type="default",
    ),
    dcc.Store(id="trips-refresh-trigger", data=0),
], fluid=True)


@callback(
    Output("trips-list", "children"),
    Input("trips-refresh-trigger", "data"),
)
def load_trips(_):
    try:
        trips = api_client.list_trips()
        return make_trip_cards(trips)
    except Exception as e:
        return dbc.Alert(f"Error fetching trips: {str(e)}", color="danger")


@callback(
    Output("trips-refresh-trigger", "data"),
    Input({"type": "delete-trip", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def delete_trip(n_clicks_list):
    if not any(n_clicks_list):
        return dash.no_update

    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        trip_id = triggered["index"]
        try:
            api_client.delete_trip(trip_id)
        except Exception:
            pass

    import time
    return int(time.time())
