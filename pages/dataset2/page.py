# pages/dataset2/page.py
# Placeholder — create datasets/dataset2.toml when dataset 2 is ready.
import dash
from dash import html

dash.register_page(__name__, path="/dataset2", title="dataset2 // coldparse")


def layout():
    return html.Div(
        className="ds-page",
        children=[
            html.Div(className="ds-no-data", children=[
                html.Span("⚠", className="ds-no-data-icon"),
                html.P("Dataset 2 not configured yet."),
                html.P(
                    "Create datasets/dataset2.toml and update this page.",
                    className="ds-no-data-hint",
                ),
            ])
        ],
    )
