# server.py
import os
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify, abort, redirect, url_for
import pandas as pd
from sqlalchemy import create_engine, text

from ui import ERR_TPL, INDEX_TPL, SUBPAGE_TPL, ITEM_TPL

app = Flask(__name__)

# =========================
# DB ENGINE
# =========================
DATABASE_DSN = os.getenv(
    "DATABASE_DSN",
    "postgresql+psycopg://postgres.avcznjglmqhmzqtsrlfg:Czheyuan0227@"
    "aws-0-us-east-2.pooler.supabase.com:6543/postgres?sslmode=require"
)
engine = create_engine(DATABASE_DSN, pool_pre_ping=True)

# =========================
# Data cache
# =========================
SO_INV: pd.DataFrame | None = None
NAV: pd.DataFrame | None = None
OPEN_PO: pd.DataFrame | None = None
_LAST_LOAD_ERR: str | None = None
_LAST_LOADED_AT: datetime | None = None

TABLE_HEADER_LABELS = {
    "Item": "Item",
    "Qty(-)": "Qty (-)",
    "Available": "Available",
    "Available + Pre-installed PO": "Avail + Pre-PO",
    "On Hand": "On Hand",
    "On Sales Order": "On SO",
    "On PO": "On PO",
    "Assigned Q'ty": "Assigned Qty",
    "On Hand - WIP": "On Hand - WIP",
    "Available + On PO": "Avail + On PO",
    "Sales/Week": "Sales / Week",
    "Recommended Restock Qty": "Restock Qty",
    "Component_Status": "Status",
    "Ship Date": "Ship Date",
}

# -------- helpers --------
def _safe_date_col(df: pd.DataFrame, col: str):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

def _to_date_str(s: pd.Series, fmt="%Y-%m-%d") -> pd.Series:
    s = pd.to_datetime(s, errors="coerce")
    return s.apply(lambda x: x.strftime(fmt) if pd.notnull(x) else "")

def _read_table(schema: str, table: str) -> pd.DataFrame:
    sql = f'SELECT * FROM "{schema}"."{table}"'
    return pd.read_sql_query(text(sql), con=engine)

def _load_from_db(force: bool = False):
    global SO_INV, NAV, OPEN_PO, _LAST_LOAD_ERR, _LAST_LOADED_AT
    try:
        if force or SO_INV is None or NAV is None or OPEN_PO is None:
            so = _read_table("public", "wo_structured")
            nav = _read_table("public", "NT Shipping Schedule")
            open_po = _read_table("public", "Open_Purchase_Orders")

            for c in ("Ship Date", "Order Date"):
                _safe_date_col(so, c)
                _safe_date_col(nav, c)
            for col in open_po.columns:
                if "date" in col.lower():
                    _safe_date_col(open_po, col)

            SO_INV, NAV, OPEN_PO = so, nav, open_po
            _LAST_LOAD_ERR = None
            _LAST_LOADED_AT = datetime.now()
    except Exception as e:
        SO_INV = None
        NAV = None
        OPEN_PO = None
        _LAST_LOAD_ERR = f"DB load error: {e}"

def _ensure_loaded():
    if SO_INV is None or NAV is None or OPEN_PO is None:
        _load_from_db(force=True)

def lookup_on_po_by_item(item: str) -> int | None:
    df = SO_INV[SO_INV["Item"] == item]
    if "On PO" not in df.columns:
        return None
    s = pd.to_numeric(df["On PO"], errors="coerce").dropna()
    return int(s.iloc[0]) if not s.empty else None

def _coerce_total(val):
    if pd.isna(val):
        return None
    as_float = float(val)
    return int(as_float) if as_float.is_integer() else as_float

def _aggregate_metric(series: pd.Series) -> int | float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    first = numeric.iloc[0]
    if numeric.eq(first).all():
        return _coerce_total(first)
    total = numeric.sum()
    return _coerce_total(total)

def _so_table_for_item(item: str) -> tuple[list[str], list[dict], dict[str, int | float | None]]:
    need_cols = ["Name", "QB Num", "Item", "Qty(-)", "Ship Date", "Picked"]
    g = SO_INV[SO_INV["Item"] == item].copy()
    for c in need_cols:
        if c not in g.columns:
            g[c] = ""
    if "Ship Date" in g.columns:
        ship_dates = pd.to_datetime(g["Ship Date"], errors="coerce")
        g = (
            g.assign(_ship_date_sort=ship_dates)
            .sort_values("_ship_date_sort", na_position="last")
            .drop(columns="_ship_date_sort")
        )
        g["Ship Date"] = _to_date_str(g["Ship Date"])
    rows = g[need_cols].fillna("").astype(str).to_dict(orient="records") if not g.empty else []
    totals = {"on_sales_order": None, "on_po": None}
    if not g.empty:
        if "On Sales Order" in g.columns:
            totals["on_sales_order"] = _aggregate_metric(g["On Sales Order"])
        if "On PO" in g.columns:
            totals["on_po"] = _aggregate_metric(g["On PO"])
    return need_cols, rows, totals

def _po_table_for_item(item: str) -> tuple[list[str], list[dict]]:
    if "Item" not in NAV.columns:
        raise ValueError("NAV table missing 'Item' column.")
    item_lower = item.lower()
    item_upper = item.upper()
    nav_item_series = NAV["Item"].astype(str)
    mask = nav_item_series.str.lower() == item_lower
    allow_desc_lookup = not item_upper.startswith(("N", "SEMIL", "POC"))
    if allow_desc_lookup and "Description" in NAV.columns:
        desc_mask = NAV["Description"].astype(str).str.lower().str.contains(item_lower, na=False)
        mask |= desc_mask
    g = NAV[mask].copy()
    for dc in ("Ship Date", "Order Date", "ETA"):
        if dc in g.columns:
            g[dc] = _to_date_str(g[dc])
    cols = list(g.columns) if not g.empty else list(NAV.columns)
    g = g.fillna("").astype(str)
    rows = g[cols].to_dict(orient="records") if not g.empty else []
    return cols, rows

def _open_po_table_for_item(item: str) -> tuple[list[str], list[dict]]:
    if OPEN_PO is None or OPEN_PO.empty:
        return [], []

    item_lower = item.lower()
    item_upper = item.upper()

    df = OPEN_PO
    item_col = next((c for c in df.columns if c.lower() == "item"), None)
    desc_col = next((c for c in df.columns if c.lower() == "description"), None)

    if item_col is None and desc_col is None:
        return list(df.columns), []

    mask = pd.Series(False, index=df.index)
    if item_col:
        mask |= df[item_col].astype(str).str.lower() == item_lower

    allow_desc_lookup = not item_upper.startswith(("N", "SEMIL", "POC"))
    if allow_desc_lookup and desc_col:
        mask |= df[desc_col].astype(str).str.lower().str.contains(item_lower, na=False)

    result = df.loc[mask].copy()
    if result.empty:
        return list(df.columns), []

    for col in result.columns:
        if "date" in col.lower():
            _safe_date_col(result, col)

    result = result.fillna("").astype(str)
    return list(result.columns), result.to_dict(orient="records")

# initial load
_load_from_db(force=True)

# =========================
# Routes
# =========================
@app.route("/", methods=["GET", "POST"])
def index():
    if request.args.get("reload") == "1":
        _load_from_db(force=True)
    _ensure_loaded()
    if _LAST_LOAD_ERR:
        return render_template_string(ERR_TPL, error=_LAST_LOAD_ERR), 503

    # ---- read inputs (work with GET or POST) ----
    so_input   = (request.values.get("so") or "").strip()
    item_input = (request.values.get("item") or "").strip()

    # If item is provided, jump straight to combined item details
    if item_input:
        return redirect(url_for("item_details", item=item_input))

    # Flexible SO handling: allow "20251368" or "so-20251368"
    so_num = so_input.upper()
    if so_num and not so_num.startswith("SO-"):
        so_num = f"SO-{so_num}"

    rows, count = None, 0
    order_summary = None
    table_headers = None
    if so_num:
        mask = SO_INV["QB Num"].astype(str).str.upper() == so_num
        rows_df = SO_INV.loc[mask].copy()
        count = len(rows_df)

        if "On Hand - WIP" not in rows_df.columns and "In Stock(Inventory)" in rows_df.columns:
            rows_df["On Hand - WIP"] = rows_df["In Stock(Inventory)"]

        required_headers = [
            "Order Date","Name","P. O. #","QB Num","Item","Qty(-)","Available",
            "Available + Pre-installed PO","On Hand","On Sales Order","On PO",
            "Assigned Q'ty","On Hand - WIP","Available + On PO","Sales/Week",
            "Recommended Restock Qty","Component_Status","Ship Date"
        ]
        for h in required_headers:
            if h not in rows_df.columns: rows_df[h] = ""
        summary_cols = ["Order Date", "Name", "P. O. #", "QB Num", "Ship Date"]
        summary_fields = []
        for col in summary_cols:
            col_vals = rows_df[col].dropna().astype(str) if col in rows_df.columns else pd.Series(dtype=str)
            summary_fields.append({
                "label": col,
                "value": col_vals.iloc[0] if not col_vals.empty else "",
            })
        order_summary = {
            "qb_num": so_num,
            "row_count": count,
            "fields": summary_fields,
        }

        for c in ("Ship Date", "Order Date"):
            if c in rows_df.columns: rows_df[c] = _to_date_str(rows_df[c])
        table_headers = [h for h in required_headers if h not in ("Order Date","Name","P. O. #","QB Num","Ship Date")]
        table_df = rows_df[table_headers].copy()
        rows = table_df.fillna("").astype(str).to_dict(orient="records")

    return render_template_string(
        INDEX_TPL,
        so_num=so_input,           # show original entry
        item_val=item_input,
        rows=rows,
        count=count,
        loaded_at=_LAST_LOADED_AT.strftime("%Y-%m-%d %H:%M:%S") if _LAST_LOADED_AT else "—",
        order_summary=order_summary,
        headers=table_headers,
        header_labels=TABLE_HEADER_LABELS,
        numeric_cols=[
            "Qty(-)","Available","Available + Pre-installed PO","On Hand",
            "On Sales Order","On PO","Assigned Q'ty","On Hand - WIP",
            "Available + On PO","Sales/Week","Recommended Restock Qty"
        ],
    )

@app.route("/api/reload", methods=["POST"])
def api_reload():
    _load_from_db(force=True)
    if _LAST_LOAD_ERR:
        return jsonify({"ok": False, "error": _LAST_LOAD_ERR}), 500
    return jsonify({"ok": True, "loaded_at": _LAST_LOADED_AT.isoformat()})

@app.route("/api/item_overview")
def api_item_overview():
    _ensure_loaded()
    if _LAST_LOAD_ERR:
        return jsonify({"ok": False, "error": _LAST_LOAD_ERR}), 503

    item = (request.args.get("item") or "").strip()
    if not item:
        abort(400, "Missing item")

    columns_so, rows_so, so_totals = _so_table_for_item(item)
    try:
        columns_po, rows_po = _po_table_for_item(item)
        open_po_cols, open_po_rows = _open_po_table_for_item(item)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    on_po_val = lookup_on_po_by_item(item)

    return jsonify(
        {
            "ok": True,
            "item": item,
            "so": {
                "columns": columns_so,
                "rows": rows_so,
                "total_on_sales": so_totals.get("on_sales_order"),
                "total_on_po": so_totals.get("on_po"),
            },
            "po": {
                "columns": columns_po,
                "rows": rows_po,
            },
            "open_po": {
                "columns": open_po_cols,
                "rows": open_po_rows,
            },
            "on_po_label": on_po_val,
        }
    )

@app.route("/so_lines")
def so_lines():
    _ensure_loaded()
    if _LAST_LOAD_ERR:
        return render_template_string(ERR_TPL, error=_LAST_LOAD_ERR), 503

    item = (request.args.get("item") or "").strip()
    if not item:
        abort(400, "Missing item")

    columns, rows, _ = _so_table_for_item(item)

    on_po_val = lookup_on_po_by_item(item)

    return render_template_string(
        SUBPAGE_TPL,
        title=f"On Sales Order — {item}",
        columns=columns,
        rows=rows,
        extra_note="Source: public.wo_structured",
        on_po=on_po_val,
        open_po_columns=[],
        open_po_rows=[],
        extra_note_open_po='Source: public.Open_Purchase_Orders',
    )

@app.route("/po_lines")
def po_lines():
    _ensure_loaded()
    if _LAST_LOAD_ERR:
        return render_template_string(ERR_TPL, error=_LAST_LOAD_ERR), 503

    item = (request.args.get("item") or "").strip()
    if not item:
        abort(400, "Missing item")

    try:
        cols, rows = _po_table_for_item(item)
        open_cols, open_rows = _open_po_table_for_item(item)
    except ValueError as exc:
        return render_template_string(ERR_TPL, error=str(exc)), 500

    on_po_val = lookup_on_po_by_item(item)

    return render_template_string(
        SUBPAGE_TPL,
        title=f"On PO — {item}",
        columns=cols,
        rows=rows,
        extra_note='Source: public."NT Shipping Schedule"',
        on_po=on_po_val,
        open_po_columns=open_cols,
        open_po_rows=open_rows,
        extra_note_open_po='Source: public.Open_Purchase_Orders',
    )

@app.route("/item_details")
def item_details():
    _ensure_loaded()
    if _LAST_LOAD_ERR:
        return render_template_string(ERR_TPL, error=_LAST_LOAD_ERR), 503

    item = (request.args.get("item") or "").strip()
    if not item:
        abort(400, "Missing item")

    columns_so, rows_so, so_totals = _so_table_for_item(item)
    try:
        columns_po, rows_po = _po_table_for_item(item)
        open_po_cols, open_po_rows = _open_po_table_for_item(item)
    except ValueError as exc:
        return render_template_string(ERR_TPL, error=str(exc)), 500

    on_po_val = lookup_on_po_by_item(item)

    return render_template_string(
        ITEM_TPL,
        item=item,
        on_po=on_po_val,
        so_columns=columns_so,
        so_rows=rows_so,
        po_columns=columns_po,
        po_rows=rows_po,
        open_po_columns=open_po_cols,
        open_po_rows=open_po_rows,
        extra_note_so="Source: public.wo_structured",
        extra_note_po='Source: public."NT Shipping Schedule"',
        extra_note_open_po='Source: public.Open_Purchase_Orders',
        so_total_on_sales=so_totals.get("on_sales_order"),
        so_total_on_po=so_totals.get("on_po"),
    )

if __name__ == "__main__":
    # Flask dev server
    app.run(debug=True, host="0.0.0.0", port=5002)
