# pages/not_found_404.py
from dash import html, register_page
import dash_bootstrap_components as dbc

# No path= argument — Dash uses this file as the 404 handler automatically.
register_page(__name__, title="404 — coldparse", external_stylesheets=[dbc.themes.BOOTSTRAP])

layout = html.Div(
    className="page-wrapper fade-up",
    children=[
        html.Div(
            className="page-header",
            children=[
                html.P("// error", className="page-eyebrow"),
                html.H1(
                    ["4", html.Span("04", className="accent")],
                    className="page-title",
                ),
                html.P("Page not found.", className="page-subtitle"),
            ],
        ),
        html.Div(
            className="wip-card",
            children=[
                html.P("dead end", className="wip-label"),
                html.P("This page doesn't exist", className="wip-title"),
                html.P(
                    "The URL you requested isn't here. "
                    "Check the address or use the sidebar to navigate.",
                    className="wip-desc",
                ),
                html.A("← back to home", href="/", className="wip-back-link"),
            ],
        ),
    ],
)
