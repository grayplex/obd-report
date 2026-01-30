import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

dash.register_page(__name__, path="/", title="OBD2 Telemetry Dashboard")

layout = dbc.Container([
    html.H1("OBD2 Telemetry Dashboard", className="mb-4"),
    dcc.Markdown("""
Welcome to the OBD2 Telemetry Dashboard. This application allows you to:

- **Upload** CSV files from your OBD2 data logger
- **Browse** your recorded trips
- **Visualize** speed, throttle, and other sensor data
- **View** GPS routes on interactive maps
- **Compare** multiple trips side by side
- **Export** reports as PDF via the print function

Use the navigation bar above to get started.
    """),
], fluid=True)
