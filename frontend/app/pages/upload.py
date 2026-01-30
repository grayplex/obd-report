import base64
import io

import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Input, Output, State

from app.api_client import api_client

dash.register_page(__name__, path="/upload", title="Upload - OBD2")

layout = dbc.Container([
    html.H1("Upload CSV File", className="mb-3"),
    dcc.Markdown("""
Upload a CSV file from your OBD2 data logger. The file should contain:
- A header comment with `# StartTime = MM/DD/YYYY HH:MM:SS.xxxx AM/PM`
- Column headers including Time, Vehicle speed, GPS coordinates, and sensor data
    """),

    dcc.Upload(
        id="upload-csv",
        children=dbc.Card(
            dbc.CardBody([
                html.I(className="bi bi-cloud-upload fs-1"),
                html.P("Drag and drop or click to select a CSV file", className="mt-2 mb-0"),
            ], className="text-center py-4"),
            className="border-dashed",
            style={"borderStyle": "dashed", "cursor": "pointer"},
        ),
        multiple=False,
        accept=".csv",
    ),

    html.Div(id="upload-filename", className="mt-2"),

    dbc.Row([
        dbc.Col([
            dbc.Label("Trip Name (optional)"),
            dbc.Input(id="trip-name", placeholder="e.g., Morning Commute"),
        ], md=6),
        dbc.Col([
            dbc.Label("Description (optional)"),
            dbc.Textarea(id="trip-description", placeholder="Add notes about this trip..."),
        ], md=6),
    ], className="mt-3"),

    dbc.Button("Upload", id="upload-button", color="primary", className="mt-3", disabled=True),
    dcc.Loading(
        html.Div(id="upload-result", className="mt-3"),
        type="default",
    ),

    html.Div(id="file-preview", className="mt-4"),
], fluid=True)


@callback(
    Output("upload-filename", "children"),
    Output("upload-button", "disabled"),
    Output("file-preview", "children"),
    Input("upload-csv", "filename"),
    Input("upload-csv", "contents"),
)
def show_filename(filename, contents):
    if filename is None:
        return "", True, ""

    # Show file preview
    preview = ""
    if contents:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string).decode("utf-8-sig")
        lines = decoded.split("\n")[:20]
        preview = [
            html.H4("File Preview"),
            dcc.Markdown(f"```\n{chr(10).join(lines)}\n```"),
        ]

    return (
        dbc.Alert(f"Selected: {filename}", color="info", className="mt-2"),
        False,
        preview,
    )


@callback(
    Output("upload-result", "children"),
    Input("upload-button", "n_clicks"),
    State("upload-csv", "contents"),
    State("upload-csv", "filename"),
    State("trip-name", "value"),
    State("trip-description", "value"),
    prevent_initial_call=True,
)
def upload_file(n_clicks, contents, filename, name, description):
    if not contents or not filename:
        return dbc.Alert("No file selected.", color="warning")

    try:
        content_type, content_string = contents.split(",")
        decoded = base64.b64decode(content_string)
        file_obj = io.BytesIO(decoded)
        file_obj.name = filename

        class FileWrapper:
            def __init__(self, data, fname):
                self.data = data
                self.name = fname
            def getvalue(self):
                return self.data

        wrapper = FileWrapper(decoded, filename)
        result = api_client.upload_csv(
            file=wrapper,
            name=name if name else None,
            description=description if description else None,
        )

        max_speed = result.get("max_speed_mph")
        avg_speed = result.get("avg_speed_mph")

        return html.Div([
            dbc.Alert("Trip uploaded successfully!", color="success"),
            html.H4("Trip Summary"),
            dbc.Row([
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.P("Duration", className="text-muted mb-0"),
                    html.H5(f"{result['duration_seconds'] / 60:.1f} min"),
                ])), md=3),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.P("Max Speed", className="text-muted mb-0"),
                    html.H5(f"{max_speed:.1f} mph" if max_speed else "N/A"),
                ])), md=3),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.P("Avg Speed", className="text-muted mb-0"),
                    html.H5(f"{avg_speed:.1f} mph" if avg_speed else "N/A"),
                ])), md=3),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.P("Data Points", className="text-muted mb-0"),
                    html.H5(f"{result.get('row_count', 0):,}"),
                ])), md=3),
            ]),
            dbc.Alert(
                dcc.Link("View your trip in the Dashboard", href=f"/dashboard?trip_id={result['id']}"),
                color="info", className="mt-3",
            ),
        ])
    except Exception as e:
        return dbc.Alert(f"Error uploading file: {str(e)}", color="danger")
