import os

import dash
import dash_bootstrap_components as dbc
from dash import html, Input, Output

from app.components.navbar import create_navbar
from app.components.print_layout import get_print_css

_here = os.path.dirname(os.path.abspath(__file__))

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    pages_folder=os.path.join(_here, "pages"),
)

# Inject print CSS into index_string
app.index_string = f'''
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}
        <style>
        {get_print_css()}
        </style>
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>
'''

app.layout = html.Div([
    create_navbar(),
    dbc.Container(
        dash.page_container,
        fluid=True,
        className="px-4",
    ),
])


# Navbar toggler callback for mobile
@app.callback(
    Output("navbar-collapse", "is_open"),
    Input("navbar-toggler", "n_clicks"),
    dash.State("navbar-collapse", "is_open"),
)
def toggle_navbar(n_clicks, is_open):
    if n_clicks:
        return not is_open
    return is_open


server = app.server

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501, debug=False)
