import dash_bootstrap_components as dbc
from dash import html


def create_navbar():
    return dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand(
                    [html.Span("OBD2 Telemetry Dashboard")],
                    href="/",
                    className="fw-bold",
                ),
                dbc.NavbarToggler(id="navbar-toggler"),
                dbc.Collapse(
                    dbc.Nav(
                        [
                            dbc.NavItem(dbc.NavLink("Home", href="/")),
                            dbc.NavItem(dbc.NavLink("Upload", href="/upload")),
                            dbc.NavItem(dbc.NavLink("Trips", href="/trips")),
                            dbc.NavItem(dbc.NavLink("Dashboard", href="/dashboard")),
                            dbc.NavItem(dbc.NavLink("Compare", href="/compare")),
                        ],
                        navbar=True,
                    ),
                    id="navbar-collapse",
                    navbar=True,
                ),
            ],
            fluid=True,
        ),
        color="dark",
        dark=True,
        className="mb-4 no-print",
    )
