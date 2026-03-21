# components/dataset_page.py
# The page engine. Reads a TOML config, queries _raw and _clean,
# builds the full scrollytelling layout. Called by page files only.

import os
try:
    import tomllib
except ImportError:
    import tomli as tomllib
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from dash import html
from components.charts import build_chart
from components.exploration import (
    compute_shape,
    compute_duplicates,
    compute_duplicates_heuristic,
    compute_col_summary,
    compute_numeric_summary,
    compute_categorical_summary,
    compute_linearity,
    compute_col_stats,
    compute_value_counts,
    make_table,
)

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "/data/coldparse.db")


# ── Default metrics per dtype ─────────────────────────────
# If a repair step declares stats but no metrics list,
# these defaults are used based on the column's dtype.

_DEFAULT_NUMERIC_METRICS  = ["row_count", "null_count", "null_pct", "mean", "std", "min", "max"]
_DEFAULT_CATEGORY_METRICS = ["row_count", "null_count", "null_pct", "unique"]


# ── DB helper ─────────────────────────────────────────────

def _load(table: str) -> pd.DataFrame | None:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        return df if not df.empty else None
    except Exception:
        return None


def _load_config(toml_path: str) -> dict:
    with open(toml_path, "rb") as f:
        return tomllib.load(f)


# ── Layout primitives ─────────────────────────────────────

def _section(label: str, children: list, cls: str = "") -> html.Div:
    return html.Div(
        className=f"ds-section {cls}".strip(),
        children=[
            html.Div(className="ds-section-marker", children=[
                html.Span(className="ds-section-line"),
                html.Span(label, className="ds-section-label"),
            ]),
            html.Div(
                className="ds-section-body",
                children=[c for c in children if c is not None],
            ),
        ],
    )


def _no_data(table: str) -> html.Div:
    return html.Div(className="ds-no-data", children=[
        html.Span("⚠", className="ds-no-data-icon"),
        html.P(f"Table '{table}' not found in database."),
        html.P(
            "Run the ingest pipeline and upload coldparse.db to the VPS.",
            className="ds-no-data-hint",
        ),
    ])


def _kv(label: str, value: str) -> html.Div:
    return html.Div(className="ds-kv", children=[
        html.Span(label, className="ds-kv-label"),
        html.Span(value, className="ds-kv-value"),
    ])


def _card(title: str, children) -> html.Div:
    return html.Div(className="ds-card", children=[
        html.H4(title, className="ds-card-title"),
        html.Div(className="ds-card-body", children=children),
    ])


def _delta_row(label: str, raw_val, clean_val, lower_is_better: bool = True) -> html.Div:
    """Single before → after row with a directional indicator."""
    try:
        raw_n   = float(str(raw_val).replace(",", "").replace("%", ""))
        clean_n = float(str(clean_val).replace(",", "").replace("%", ""))
        delta   = clean_n - raw_n
        if delta == 0:
            direction, symbol = "neutral", "→"
        elif (delta < 0) == lower_is_better:
            direction = "good"
            symbol    = "↓" if delta < 0 else "↑"
        else:
            direction = "warn"
            symbol    = "↓" if delta < 0 else "↑"
    except Exception:
        direction, symbol = "neutral", "→"

    return html.Div(className=f"ds-delta ds-delta-{direction}", children=[
        html.Span(label,          className="ds-delta-label"),
        html.Span(str(raw_val),   className="ds-delta-raw"),
        html.Span(symbol,         className="ds-delta-arrow"),
        html.Span(str(clean_val), className="ds-delta-clean"),
    ])


# ── Repair comparison renderers ───────────────────────────

_METRIC_LABELS = {
    "row_count":  "row count",
    "null_count": "null count",
    "null_pct":   "null %",
    "unique":     "unique values",
    "mean":       "mean",
    "std":        "std dev",
    "min":        "min",
    "max":        "max",
    "median":     "median",
}

_LOWER_IS_BETTER = {"null_count", "null_pct"}
_HIGHER_IS_BETTER = {"row_count", "unique", "mean", "median", "min", "max"}


def _render_stats(
    df_raw:   pd.DataFrame,
    df_clean: pd.DataFrame,
    columns:  list[str],
    metrics:  list[str] | None,
) -> html.Div:
    """
    For each column in columns, compute requested metrics on both
    df_raw and df_clean and render as a before/after delta card.
    If a column was dropped in clean, show 'dropped' as the clean value.
    If metrics is None, default by dtype.
    """
    cards = []

    for col in columns:
        col_exists_raw   = col in df_raw.columns
        col_exists_clean = col in df_clean.columns

        # Determine metrics to show
        if metrics:
            col_metrics = metrics
        elif col_exists_raw and pd.api.types.is_numeric_dtype(df_raw[col]):
            col_metrics = _DEFAULT_NUMERIC_METRICS
        else:
            col_metrics = _DEFAULT_CATEGORY_METRICS

        # row_count is table-level, not column-level — use it once
        # but still show it if declared
        raw_stats   = compute_col_stats(df_raw,   col, col_metrics)
        clean_stats = compute_col_stats(df_clean, col, col_metrics) if col_exists_clean else {}

        delta_rows = []
        for m in col_metrics:
            raw_val   = raw_stats.get(m, "—")
            if not col_exists_clean:
                clean_val = "dropped"
                lower_ok  = True
            else:
                clean_val = clean_stats.get(m, "—")
                lower_ok  = m in _LOWER_IS_BETTER

            delta_rows.append(_delta_row(
                _METRIC_LABELS.get(m, m),
                raw_val,
                clean_val,
                lower_is_better=lower_ok,
            ))

        label = col if col_exists_clean else f"{col} (dropped)"
        cards.append(_card(label, html.Div(className="ds-delta-group", children=delta_rows)))

    return html.Div(className="ds-comparison-stats", children=cards)


def _render_value_counts(
    df_raw:   pd.DataFrame,
    df_clean: pd.DataFrame,
    columns:  list[str],
    top_n:    int = 5,
) -> html.Div:
    """
    Side-by-side top N value counts for each column in columns.
    """
    blocks = []
    for col in columns:
        raw_vc   = compute_value_counts(df_raw,   col, top_n)
        clean_vc = compute_value_counts(df_clean, col, top_n) if col in df_clean.columns else []

        blocks.append(html.Div(className="ds-vc-block", children=[
            html.Span(col, className="ds-vc-col-label"),
            html.Div(className="ds-vc-tables", children=[
                html.Div(children=[
                    html.Span("raw",   className="ds-vc-side-label"),
                    make_table(raw_vc, ["Value", "Count", "% of rows"]),
                ]),
                html.Div(children=[
                    html.Span("clean", className="ds-vc-side-label"),
                    make_table(clean_vc, ["Value", "Count", "% of rows"])
                    if clean_vc else html.P("Column dropped.", className="ds-empty-note"),
                ]),
            ]),
        ]))

    return html.Div(className="ds-comparison-vc", children=blocks)


def _render_repair_charts(
    df_raw:    pd.DataFrame,
    df_clean:  pd.DataFrame,
    columns:   list[str],
    chart_cfg: dict,
) -> html.Div:
    """
    Side-by-side chart for each column in columns — raw left, clean right.
    chart_cfg declares chart_type and any overrides; col is injected per column.
    """
    pairs = []
    for col in columns:
        # For box/histogram, only y matters — don't inject x as grouping axis
        chart_type = chart_cfg.get("chart_type", "")
        if chart_type in ("box", "histogram", "hist"):
            raw_cfg   = {**chart_cfg, "col": col, "y": col, "title": f"{col} — raw"}
            clean_cfg = {**chart_cfg, "col": col, "y": col, "title": f"{col} — clean"}
        else:
            raw_cfg   = {**chart_cfg, "col": col, "x": col, "y": col, "title": f"{col} — raw"}
            clean_cfg = {**chart_cfg, "col": col, "x": col, "y": col, "title": f"{col} — clean"}

        try:
            raw_chart = build_chart(df_raw, {**raw_cfg, "type": chart_cfg["chart_type"]})
        except Exception as e:
            raw_chart = html.P(f"Chart error (raw): {e}", className="ds-empty-note")

        try:
            clean_chart = build_chart(df_clean, {**clean_cfg, "type": chart_cfg["chart_type"]}) \
                if col in df_clean.columns \
                else html.P("Column dropped.", className="ds-empty-note")
        except Exception as e:
            clean_chart = html.P(f"Chart error (clean): {e}", className="ds-empty-note")

        pairs.append(html.Div(className="ds-repair-chart-pair", children=[
            html.Div(children=[
                html.Span("raw",   className="ds-vc-side-label"),
                raw_chart,
            ]),
            html.Div(children=[
                html.Span("clean", className="ds-vc-side-label"),
                clean_chart,
            ]),
        ]))

    return html.Div(className="ds-comparison-charts", children=pairs)


# ── Section builders ──────────────────────────────────────

def _build_intro(cfg: dict) -> html.Div:
    return _section("01 // introduction", [
        html.H1(cfg["label"], className="ds-title"),
        html.Div(className="ds-meta-row", children=[
            _kv("source", cfg["source"]),
            _kv("table",  cfg["table"]),
        ]),
        html.P(cfg["context"].strip(), className="ds-context"),
        html.Div(className="ds-question-block", children=[
            html.Span("the question", className="ds-question-eyebrow"),
            html.P(cfg["question"].strip(), className="ds-question-text"),
        ]),
    ], cls="ds-section-intro")


def _build_raw_profile(df_raw: pd.DataFrame | None, table: str) -> html.Div:
    if df_raw is None:
        return _section("02 // raw profile", [_no_data(f"{table}_raw")])

    shape  = compute_shape(df_raw)
    dupes  = compute_duplicates(df_raw)
    hdupes = compute_duplicates_heuristic(df_raw)
    cols   = compute_col_summary(df_raw)
    nums   = compute_numeric_summary(df_raw)
    cats   = compute_categorical_summary(df_raw)
    lin    = compute_linearity(df_raw)

    excl_note = f"excluding: {', '.join(hdupes['excluded_cols'])}" if hdupes["excluded_cols"] else "no columns excluded"

    return _section("02 // raw profile", [
        html.Div(className="ds-card-row", children=[
            _card("shape", [
                html.Div(className="ds-dupe-row", children=[
                    html.Div(className="ds-dupe-col", children=[
                        html.Span("rows",        className="ds-dupe-label"),
                        html.Span(shape["rows"], className="ds-dupe-value"),
                    ]),
                    html.Div(className="ds-dupe-col", children=[
                        html.Span("columns",     className="ds-dupe-label"),
                        html.Span(shape["cols"], className="ds-dupe-value"),
                    ]),
                    html.Div(className="ds-dupe-col", children=[
                        html.Span("memory",        className="ds-dupe-label"),
                        html.Span(shape["mem_kb"], className="ds-dupe-value"),
                    ]),
                ]),
            ]),
            _card("duplicates", [
                html.Div(className="ds-dupe-row", children=[
                    html.Div(className="ds-dupe-col", children=[
                        html.Span("exact",          className="ds-dupe-label"),
                        html.Span(dupes["count"],   className="ds-dupe-value"),
                        html.Span(dupes["pct"],     className="ds-dupe-pct"),
                    ]),
                    html.Div(className="ds-dupe-col", children=[
                        html.Span("substantive",             className="ds-dupe-label"),
                        html.Span(hdupes["heuristic_count"], className="ds-dupe-value"),
                        html.Span(hdupes["heuristic_pct"],   className="ds-dupe-pct"),
                    ]),
                    html.Div(className="ds-dupe-col", children=[
                        html.Span("total duplicates",     className="ds-dupe-label"),
                        html.Span(hdupes["union_count"],  className="ds-dupe-value"),
                        html.Span(hdupes["union_pct"],    className="ds-dupe-pct"),
                    ]),
                ]),
            ]),
        ]),
        _card("columns",         make_table(cols, ["Column", "Dtype", "Nulls", "Null %", "Unique"])),
        _card("numeric summary", make_table(nums, ["Column", "Min", "Max", "Mean", "Median", "Std"])) if nums else None,
        _card("categorical",     make_table(cats, ["Column", "Unique", "Top 3 Values"]))              if cats else None,
        _card("top linear pairs (R²)", [
            html.P(
                "Computed on pairwise complete observations. Nulls excluded per pair.",
                className="ds-card-note",
            ),
            make_table(lin, ["Column A", "Column B", "R²"]),
        ]) if lin else None,
    ], cls="ds-section-profile")


def _build_repair(
    df_raw:   pd.DataFrame | None,
    df_clean: pd.DataFrame | None,
    cfg:      dict,
) -> html.Div:

    # If either table is missing, still show the authored steps
    # but skip any auto-computed comparisons
    have_both = df_raw is not None and df_clean is not None

    children = []

    # ── Overall before/after summary ──────────────────────
    if have_both:
        raw_shape   = compute_shape(df_raw)
        clean_shape = compute_shape(df_clean)
        children.append(html.Div(className="ds-card-row", children=[
            _card("before", [
                _kv("rows",    raw_shape["rows"]),
                _kv("columns", raw_shape["cols"]),
            ]),
            _card("after", [
                _kv("rows",    clean_shape["rows"]),
                _kv("columns", clean_shape["cols"]),
            ]),
        ]))

    # ── Per repair step ───────────────────────────────────
    for step in cfg.get("repair", []):
        columns      = step.get("columns", [])
        comparisons  = step.get("comparisons", [])
        step_nodes   = [
            html.H4(step["step"],              className="ds-repair-step-title"),
            html.P(step["explanation"].strip(), className="ds-repair-explanation"),
        ]

        if have_both:
            for comp in comparisons:
                comp_type = comp.get("type")
                top_n     = comp.get("top_n", 5)
                metrics   = comp.get("metrics")   # None = use defaults

                if comp_type == "stats":
                    step_nodes.append(
                        _render_stats(df_raw, df_clean, columns, metrics)
                    )
                elif comp_type == "value_counts":
                    step_nodes.append(
                        _render_value_counts(df_raw, df_clean, columns, top_n)
                    )
                elif comp_type == "chart":
                    step_nodes.append(
                        _render_repair_charts(df_raw, df_clean, columns, comp)
                    )

        children.append(html.Div(className="ds-repair-step", children=step_nodes))

    if not children:
        children = [html.P("No repair steps defined.", className="ds-empty-note")]

    return _section("03 // repair", children, cls="ds-section-repair")


def _build_findings(df_clean: pd.DataFrame | None, cfg: dict) -> html.Div:
    if df_clean is None:
        return _section("04 // findings", [_no_data(f"{cfg['table']}_clean")])

    children = []
    for i, finding in enumerate(cfg.get("findings", []), 1):
        chart_nodes = []
        for chart_cfg in finding.get("charts", []):
            try:
                chart_nodes.append(build_chart(df_clean, chart_cfg))
            except Exception as e:
                chart_nodes.append(html.P(f"Chart error: {e}", className="ds-empty-note"))

        children.append(html.Div(className="ds-finding", children=[
            html.Div(className="ds-finding-header", children=[
                html.Span(f"{i:02d}", className="ds-finding-number"),
                html.H3(finding["question"], className="ds-finding-question"),
            ]),
            html.P(finding["narrative"].strip(), className="ds-finding-narrative"),
            html.Div(className="ds-chart-row", children=chart_nodes),
        ]))

    if not children:
        children = [html.P("No findings defined.", className="ds-empty-note")]

    return _section("04 // findings", children, cls="ds-section-findings")


# ── Entry point ───────────────────────────────────────────

def build_dataset_page(toml_path: str) -> html.Div:
    """
    Called by each dataset page's layout() function.
    toml_path: relative path e.g. 'datasets/dataset1.toml'
    Loads config, queries _raw and _clean, returns full layout.
    DataFrames go out of scope when this function returns.
    """
    cfg      = _load_config(toml_path)
    table    = cfg["table"]
    df_raw   = _load(f"{table}_raw")
    df_clean = _load(f"{table}_clean")

    return html.Div(
        className="ds-page",
        children=[
            _build_intro(cfg),
            _build_raw_profile(df_raw, table),
            _build_repair(df_raw, df_clean, cfg),
            _build_findings(df_clean, cfg),
        ],
    )