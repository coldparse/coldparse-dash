# pages/home.py
import dash
from dash import html

dash.register_page(__name__, path="/", name="Home")


layout = html.Div(
    className="page-wrapper fade-up",
    children=[
        html.Div(
            className="page-header",
            children=[
                html.P("// overview", className="page-eyebrow"),
                html.H1(
                    ["cold", html.Span("parse", className="accent")],
                    className="page-title",
                ),
                html.P("Personal analytics dashboard. Work in progress.", className="page-subtitle"),
            ],
        ),

        # Placeholder stat cards — replace values when data is wired up
        html.Div(
            className="stat-grid",
            children=[
                html.Div(className="stat-card", children=[
                    html.Span("—", className="stat-card-value"),
                    html.Span("stat one", className="stat-card-label"),
                ]),
                html.Div(className="stat-card", children=[
                    html.Span("—", className="stat-card-value"),
                    html.Span("stat two", className="stat-card-label"),
                ]),
                html.Div(className="stat-card", children=[
                    html.Span("—", className="stat-card-value"),
                    html.Span("stat three", className="stat-card-label"),
                ]),
                html.Div(className="stat-card", children=[
                    html.Span("—", className="stat-card-value"),
                    html.Span("stat four", className="stat-card-label"),
                ]),
            ],
        ),

        html.Div(
            className="wip-card",
            children=[
                html.P("status", className="wip-label"),
                html.P("Dashboard under construction", className="wip-title"),
                html.P(
                    "Data sources and visualisations will appear here as they are built out. "
                    "Use the sidebar to navigate to available sections.",
                    className="wip-desc",
                ),
            ],
        ),
    ],
)
