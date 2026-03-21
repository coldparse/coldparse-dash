# app.py
import os
from dotenv import load_dotenv

load_dotenv()

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="coldparse // dashboard",
)
server = app.server  # expose for gunicorn


# ── Sidebar ───────────────────────────────────────────────
sidebar = html.Div(
    id="sidebar",
    children=[
        dbc.Accordion(
            [
                # ── Dataset 1 ─────────────────────────────
                dbc.AccordionItem(
                    [
                        dbc.NavLink("» Synthetic Sales", href="/dataset1", active="exact", className="sidebar-navlink"),
                    ],
                    title="Dataset 1",
                    className="sidebar-accordion-item",
                ),

                # ── Dataset 2 ─────────────────────────────
                dbc.AccordionItem(
                    [
                        dbc.NavLink("» Dataset 2", href="/dataset2", active="exact", className="sidebar-navlink"),
                    ],
                    title="Dataset 2",
                    className="sidebar-accordion-item",
                ),
            ],
            start_collapsed=True,
            flush=True,
        ),
        html.Div("coldparse // dashboard", className="sidebar-footer"),
    ],
)


# ── Top bar ───────────────────────────────────────────────
topbar = html.Div(
    id="topbar",
    children=[
        html.Button(
            id="hamburger",
            children=[html.Span(), html.Span(), html.Span()],
            n_clicks=0,
            title="Toggle navigation",
        ),
        html.A(
            [html.Span("~/"), "coldparse"],
            href="/",
            id="topbar-logo",
        ),
        html.Div(
            className="topbar-right",
            children=[
                html.Div(
                    className="topbar-status",
                    children=[html.Span(className="status-dot"), "dashboard"],
                )
            ],
        ),
    ],
)


# ── App layout ────────────────────────────────────────────
app.layout = html.Div(
    id="app-container",
    children=[
        # Global URL location — used by page callbacks as load trigger
        dcc.Location(id="url", refresh=False),

        html.Div(id="sidebar-overlay", n_clicks=0),
        topbar,
        sidebar,
        html.Div(
            id="page-content",
            children=dash.page_container,
        ),
    ],
)


# ── Clientside callbacks ──────────────────────────────────
app.clientside_callback(
    """
    function(n_clicks) {
        document.body.classList.toggle('sidebar-open');
        return null;
    }
    """,
    dash.Output("hamburger", "data-toggled"),
    dash.Input("hamburger", "n_clicks"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks) document.body.classList.remove('sidebar-open');
        return null;
    }
    """,
    dash.Output("sidebar-overlay", "data-closed"),
    dash.Input("sidebar-overlay", "n_clicks"),
    prevent_initial_call=True,
)


# ── Entry point ───────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
