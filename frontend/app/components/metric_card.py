import dash_bootstrap_components as dbc
from dash import html


def metric_card(label, value, delta=None, delta_color="normal"):
    """Create a metric card similar to st.metric.

    Args:
        label: The metric label
        value: The metric value (string)
        delta: Optional delta text
        delta_color: "normal" (green), "inverse" (red for positive delta), or "off"
    """
    children = [
        html.P(label, className="metric-label mb-0 text-muted",
               style={"fontSize": "0.85rem"}),
        html.P(value, className="metric-value mb-0 fw-bold",
               style={"fontSize": "1.5rem"}),
    ]

    if delta is not None:
        if delta_color == "inverse":
            color = "text-danger"
        elif delta_color == "normal":
            color = "text-success"
        else:
            color = "text-muted"

        children.append(
            html.P(delta, className=f"metric-delta mb-0 {color}",
                   style={"fontSize": "0.8rem"})
        )

    return dbc.Card(
        dbc.CardBody(children, className="text-center py-2"),
        className="h-100",
    )
