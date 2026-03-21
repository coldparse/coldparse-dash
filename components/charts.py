# components/charts.py
# Chart factory. Takes a chart config dict and a DataFrame, returns a dcc.Graph.
# Supports: scatter, histogram, box, bar, pie, heatmap, line, bubble.
# All charts use the coldparse dark theme.

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc

# ── Theme ─────────────────────────────────────────────────
THEME = {
    "bg":         "#070d14",
    "paper":      "#0d1821",
    "grid":       "#1a2a3a",
    "text":       "#a8c4d8",
    "accent":     "#7dd4fc",
    "accent2":    "#38bdf8",
    "warn":       "#f59e0b",
    "sequence":   ["#7dd4fc", "#38bdf8", "#0ea5e9", "#0284c7", "#f59e0b", "#34d399", "#f87171"],
    "font":       "Space Mono, monospace",
}

LAYOUT_BASE = dict(
    paper_bgcolor = THEME["paper"],
    plot_bgcolor  = THEME["bg"],
    font          = dict(family=THEME["font"], color=THEME["text"], size=11),
    margin        = dict(l=40, r=20, t=40, b=40),
    xaxis         = dict(gridcolor=THEME["grid"], zerolinecolor=THEME["grid"], color=THEME["text"]),
    yaxis         = dict(gridcolor=THEME["grid"], zerolinecolor=THEME["grid"], color=THEME["text"]),
    legend        = dict(bgcolor="rgba(0,0,0,0)", font=dict(color=THEME["text"])),
    colorway      = THEME["sequence"],
)


def _apply_theme(fig) -> go.Figure:
    fig.update_layout(**LAYOUT_BASE)
    return fig


def _graph(fig, config: dict) -> dcc.Graph:
    return dcc.Graph(
        figure=_apply_theme(fig),
        config={"displayModeBar": False},
        className=f"chart-graph chart-{config.get('type', 'unknown')}",
    )


# ── Chart builders ────────────────────────────────────────

def _scatter(df: pd.DataFrame, cfg: dict) -> dcc.Graph:
    fig = px.scatter(
        df,
        x     = cfg["x"],
        y     = cfg["y"],
        color = cfg.get("color"),
        title = cfg.get("title", f"{cfg['x']} vs {cfg['y']}"),
        trendline = "ols" if cfg.get("trendline", True) else None,
        color_discrete_sequence = THEME["sequence"],
    )
    fig.update_traces(marker=dict(size=5, opacity=0.7))
    return _graph(fig, cfg)


def _histogram(df: pd.DataFrame, cfg: dict) -> dcc.Graph:
    fig = px.histogram(
        df,
        x      = cfg["col"],
        color  = cfg.get("color"),
        nbins  = cfg.get("bins", 30),
        title  = cfg.get("title", f"Distribution — {cfg['col']}"),
        color_discrete_sequence = THEME["sequence"],
    )
    fig.update_traces(marker_line_width=0.5, marker_line_color=THEME["bg"])
    return _graph(fig, cfg)


def _box(df: pd.DataFrame, cfg: dict) -> dcc.Graph:
    fig = px.box(
        df,
        x      = cfg.get("x"),
        y      = cfg["y"],
        color  = cfg.get("color", cfg.get("x")),
        title  = cfg.get("title", f"{cfg['y']} distribution"),
        points = "outliers",
        color_discrete_sequence = THEME["sequence"],
    )
    return _graph(fig, cfg)


def _bar(df: pd.DataFrame, cfg: dict) -> dcc.Graph:
    agg_fn = cfg.get("agg", "mean")
    agg_map = {"mean": "mean", "sum": "sum", "count": "count", "median": "median"}
    grouped = df.groupby(cfg["x"])[cfg["y"]].agg(agg_map[agg_fn]).reset_index()
    grouped.columns = [cfg["x"], cfg["y"]]
    grouped = grouped.sort_values(cfg["y"], ascending=False)

    fig = px.bar(
        grouped,
        x      = cfg["x"],
        y      = cfg["y"],
        title  = cfg.get("title", f"{agg_fn.title()} {cfg['y']} by {cfg['x']}"),
        color  = cfg["x"],
        color_discrete_sequence = THEME["sequence"],
    )
    fig.update_traces(marker_line_width=0)
    return _graph(fig, cfg)


def _pie(df: pd.DataFrame, cfg: dict) -> dcc.Graph:
    if "values" in cfg:
        grouped = df.groupby(cfg["col"])[cfg["values"]].sum().reset_index()
        fig = px.pie(
            grouped,
            names  = cfg["col"],
            values = cfg["values"],
            title  = cfg.get("title", f"{cfg['col']} by {cfg['values']}"),
            color_discrete_sequence = THEME["sequence"],
        )
    else:
        fig = px.pie(
            df,
            names  = cfg["col"],
            title  = cfg.get("title", f"{cfg['col']} breakdown"),
            color_discrete_sequence = THEME["sequence"],
        )
    fig.update_traces(textfont_color=THEME["text"], marker=dict(line=dict(color=THEME["bg"], width=1.5)))
    return _graph(fig, cfg)


def _heatmap(df: pd.DataFrame, cfg: dict) -> dcc.Graph:
    if "values" in cfg:
        pivot = df.pivot_table(index=cfg["y"], columns=cfg["x"], values=cfg["values"], aggfunc="mean")
        fig = go.Figure(data=go.Heatmap(
            z          = pivot.values,
            x          = pivot.columns.tolist(),
            y          = pivot.index.tolist(),
            colorscale = [[0, THEME["bg"]], [0.5, THEME["accent2"]], [1, THEME["accent"]]],
            showscale  = True,
        ))
        fig.update_layout(title=cfg.get("title", f"{cfg['values']} by {cfg['x']} × {cfg['y']}"))
    else:
        # Correlation heatmap across numeric columns
        num_cols = cfg.get("columns") or df.select_dtypes(include="number").columns.tolist()
        corr = df[num_cols].corr()
        fig = go.Figure(data=go.Heatmap(
            z          = corr.values,
            x          = corr.columns.tolist(),
            y          = corr.index.tolist(),
            colorscale = [[0, "#f87171"], [0.5, THEME["bg"]], [1, THEME["accent"]]],
            zmid       = 0,
            showscale  = True,
        ))
        fig.update_layout(title=cfg.get("title", "Correlation matrix"))
    return _graph(fig, cfg)


def _line(df: pd.DataFrame, cfg: dict) -> dcc.Graph:
    fig = px.line(
        df,
        x      = cfg["x"],
        y      = cfg["y"],
        color  = cfg.get("color"),
        title  = cfg.get("title", f"{cfg['y']} over {cfg['x']}"),
        color_discrete_sequence = THEME["sequence"],
    )
    fig.update_traces(line=dict(width=2))
    return _graph(fig, cfg)


def _bubble(df: pd.DataFrame, cfg: dict) -> dcc.Graph:
    fig = px.scatter(
        df,
        x     = cfg["x"],
        y     = cfg["y"],
        size  = cfg["size"],
        color = cfg.get("color"),
        title = cfg.get("title", f"{cfg['x']} vs {cfg['y']} (sized by {cfg['size']})"),
        color_discrete_sequence = THEME["sequence"],
    )
    fig.update_traces(marker=dict(opacity=0.7, line=dict(width=0)))
    return _graph(fig, cfg)


# ── Dispatch ──────────────────────────────────────────────

_BUILDERS = {
    "scatter":   _scatter,
    "histogram": _histogram,
    "box":       _box,
    "bar":       _bar,
    "pie":       _pie,
    "heatmap":   _heatmap,
    "line":      _line,
    "bubble":    _bubble,
}


def build_chart(df: pd.DataFrame, cfg: dict) -> dcc.Graph:
    """
    Main entry point. Takes a DataFrame and a chart config dict.
    Returns a themed dcc.Graph ready to drop into a layout.
    """
    chart_type = cfg.get("type")
    builder = _BUILDERS.get(chart_type)
    if builder is None:
        raise ValueError(f"Unknown chart type: '{chart_type}'. Supported: {list(_BUILDERS)}")
    return builder(df, cfg)
