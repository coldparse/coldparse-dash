# components/exploration.py
# Pure compute functions. No DB access, no Dash layout, no callbacks.
# All functions take a DataFrame and return plain Python dicts/lists.
# Called by dataset_page.py — never directly.

import pandas as pd
from dash import html, dash_table


# ── Compute functions ─────────────────────────────────────

def compute_shape(df: pd.DataFrame) -> dict:
    return {
        "rows":   f"{len(df):,}",
        "cols":   f"{len(df.columns):,}",
        "mem_kb": f"{round(df.memory_usage(deep=True).sum() / 1024, 1)} KB",
    }


def compute_duplicates(df: pd.DataFrame) -> dict:
    """
    Exact duplicate rows across all columns. Pandas default behaviour.
    No assumptions about column meaning.
    """
    n = int(df.duplicated().sum())
    return {
        "count": f"{n:,}",
        "pct":   f"{round(n / len(df) * 100, 2)}%",
    }


def compute_duplicates_heuristic(df: pd.DataFrame) -> dict:
    """
    Substantive duplicate check. Drops columns that look like unique
    identifiers (name contains: id, key, uuid, ref, no, num, code)
    then checks for duplicates across the remaining columns.

    Reports:
    - heuristic_count: duplicates found after dropping ID-like columns
    - union_count: total rows flagged by either exact or heuristic check
    - excluded_cols: which columns were dropped before checking
    """
    id_patterns = ["id", "key", "uuid", "ref", "_no", "_num", "code"]
    excluded = [
        c for c in df.columns
        if any(p in c.lower() for p in id_patterns)
    ]
    check_cols = [c for c in df.columns if c not in excluded]

    if not check_cols:
        # Every column looks like an ID — fall back to full check
        check_cols = df.columns.tolist()
        excluded   = []

    heuristic_mask = df.duplicated(subset=check_cols)
    exact_mask     = df.duplicated()
    union_mask     = heuristic_mask | exact_mask

    h_count = int(heuristic_mask.sum())
    u_count = int(union_mask.sum())

    return {
        "heuristic_count": f"{h_count:,}",
        "heuristic_pct":   f"{round(h_count / len(df) * 100, 2)}%",
        "union_count":     f"{u_count:,}",
        "union_pct":       f"{round(u_count / len(df) * 100, 2)}%",
        "excluded_cols":   excluded,
    }


def compute_col_summary(df: pd.DataFrame) -> list[dict]:
    return [
        {
            "Column": col,
            "Dtype":  str(df[col].dtype),
            "Nulls":  int(df[col].isnull().sum()),
            "Null %": f"{round(df[col].isnull().sum() / len(df) * 100, 1)}%",
            "Unique": int(df[col].nunique()),
        }
        for col in df.columns
    ]


def compute_numeric_summary(df: pd.DataFrame) -> list[dict]:
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if not num_cols:
        return []
    summary = df[num_cols].agg(["min", "max", "mean", "median", "std"]).T.reset_index()
    summary.columns = ["Column", "Min", "Max", "Mean", "Median", "Std"]
    for col in ["Min", "Max", "Mean", "Median", "Std"]:
        summary[col] = summary[col].apply(lambda x: round(x, 4) if pd.notnull(x) else "—")
    return summary.to_dict("records")


def compute_categorical_summary(df: pd.DataFrame) -> list[dict]:
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    rows = []
    for col in cat_cols:
        top = df[col].value_counts().head(3)
        top_str = ", ".join([f"{v} ({c})" for v, c in top.items()])
        rows.append({
            "Column":       col,
            "Unique":       int(df[col].nunique()),
            "Top 3 Values": top_str,
        })
    return rows


def compute_linearity(df: pd.DataFrame, top_n: int = 3) -> list[dict]:
    """
    Top N numeric column pairs by R².
    Computed on pairwise complete observations — nulls excluded per pair.
    """
    num_cols = df.select_dtypes(include="number").columns.tolist()
    if len(num_cols) < 2:
        return []
    pairs = []
    for i, col_a in enumerate(num_cols):
        for col_b in num_cols[i + 1:]:
            both = df[[col_a, col_b]].dropna()
            if len(both) < 10:
                continue
            r = both[col_a].corr(both[col_b])
            if pd.notnull(r):
                pairs.append({
                    "Column A": col_a,
                    "Column B": col_b,
                    "R²":       round(r ** 2, 4),
                })
    pairs.sort(key=lambda x: x["R²"], reverse=True)
    return pairs[:top_n]


def compute_col_stats(df: pd.DataFrame, col: str, metrics: list[str]) -> dict:
    """
    Compute a specific set of metrics for one column.
    Used by the repair comparison engine.
    Supported metrics: row_count, null_count, null_pct, unique,
                       mean, std, min, max, median
    """
    results = {}
    series = df[col] if col in df.columns else None

    for m in metrics:
        if m == "row_count":
            results[m] = f"{len(df):,}"
        elif series is None:
            results[m] = "—"
        elif m == "null_count":
            results[m] = f"{int(series.isnull().sum()):,}"
        elif m == "null_pct":
            results[m] = f"{round(series.isnull().mean() * 100, 1)}%"
        elif m == "unique":
            results[m] = f"{int(series.nunique()):,}"
        elif m == "mean":
            v = pd.to_numeric(series, errors="coerce").mean()
            results[m] = f"{round(v, 2):,}" if pd.notnull(v) else "—"
        elif m == "std":
            v = pd.to_numeric(series, errors="coerce").std()
            results[m] = f"{round(v, 2):,}" if pd.notnull(v) else "—"
        elif m == "min":
            v = pd.to_numeric(series, errors="coerce").min()
            results[m] = f"{round(v, 2):,}" if pd.notnull(v) else "—"
        elif m == "max":
            v = pd.to_numeric(series, errors="coerce").max()
            results[m] = f"{round(v, 2):,}" if pd.notnull(v) else "—"
        elif m == "median":
            v = pd.to_numeric(series, errors="coerce").median()
            results[m] = f"{round(v, 2):,}" if pd.notnull(v) else "—"
        else:
            results[m] = "—"
    return results


def compute_value_counts(df: pd.DataFrame, col: str, top_n: int = 5) -> list[dict]:
    """Top N value counts for a column as a list of dicts."""
    if col not in df.columns:
        return []
    vc = df[col].value_counts().head(top_n).reset_index()
    vc.columns = ["Value", "Count"]
    vc["% of rows"] = (vc["Count"] / len(df) * 100).round(1).astype(str) + "%"
    return vc.to_dict("records")


# ── DataTable factory ─────────────────────────────────────

def make_table(records: list[dict], col_names: list[str] | None = None) -> dash_table.DataTable | html.P:
    if not records:
        return html.P("No data.", className="ds-empty-note")
    cols = col_names or list(records[0].keys())
    return dash_table.DataTable(
        data=records,
        columns=[{"name": c, "id": c} for c in cols],
        style_table={
            "overflowX":       "auto",
            "backgroundColor": "#0d1821",
            "border":          "1px solid #1a2a3a",
        },
        style_cell={
            "textAlign":       "left",
            "padding":         "6px 12px",
            "fontFamily":      "Space Mono, monospace",
            "fontSize":        "0.78rem",
            "maxWidth":        "240px",
            "overflow":        "hidden",
            "textOverflow":    "ellipsis",
            "backgroundColor": "#0d1821",
            "color":           "#a8c4d8",
            "border":          "1px solid #1a2a3a",
        },
        style_header={
            "backgroundColor": "#070d14",
            "color":           "#7dd4fc",
            "fontWeight":      "600",
            "fontFamily":      "Space Mono, monospace",
            "fontSize":        "0.72rem",
            "letterSpacing":   "0.08em",
            "textTransform":   "uppercase",
            "border":          "1px solid #1a2a3a",
        },
        style_data_conditional=[
            {
                "if":              {"row_index": "odd"},
                "backgroundColor": "#0a1520",
            },
            {
                "if":              {"state": "selected"},
                "backgroundColor": "#1a2a3a",
                "border":          "1px solid #7dd4fc",
            },
        ],
        page_size=20,
        tooltip_data=[
            {c: {"value": str(row.get(c, "")), "type": "markdown"} for c in cols}
            for row in records
        ],
        tooltip_duration=None,
    )