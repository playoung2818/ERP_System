from __future__ import annotations
import numpy as np, pandas as pd
from core import _norm_cols
import re


## 1. Transform NAV_Shipping
# ---- helpers ---------------------------------------------------------------
INCL_SPLIT = re.compile(r"\bincluding\b", re.IGNORECASE)
QTYX_RE = re.compile(r"^\s*(\d+)\s*x\s*(.+)\s*$", re.IGNORECASE) # "2x SSD-1TB"

def clean_space(s: str) -> str:
    if not isinstance(s, str):
        return ""
    # Normalize NBSP etc.
    return s.replace('\u00A0', ' ').replace('\u3000', ' ').strip()

def parse_description(desc: str) -> tuple[str, list[str]]:
    """
    Returns (parent_code, component_tokens[])
    e.g. "SEMIL-2047GC-CRL, including i9-13900E, 2x SSD-1TB"
    -> ("SEMIL-2047GC-CRL", ["i9-13900E", "2x SSD-1TB"])
    """
    s = clean_space(desc)
    parts = INCL_SPLIT.split(s, maxsplit=1)
    # parent part may have a trailing ", ..." — keep only before first comma
    parent = clean_space(parts[0].split(",")[0])
    comps = []
    if len(parts) > 1:
        comps = [clean_space(x) for x in parts[1].split(",") if clean_space(x)]
    return parent, comps

def parse_component_token(token: str) -> tuple[str, float]:
    """
    Parses pre-installed component rows, e.g. "2x SSD-1TB"
    Returns (item_code, qty_per_parent).
    """
    m = QTYX_RE.match(token)
    if m:
        qty = float(m.group(1))
        item = clean_space(m.group(2))
        return item, qty
    return clean_space(token), 1.0

def expand_preinstalled_row(row: pd.Series) -> pd.DataFrame:
    """
    For a single NAV row (Pre-installed), expand into multiple rows:
    - one row per component with Qty(+) multiplied by qty_per_parent
    - (optional) one row for the parent itself if you want to track it too
    """
    parent, tokens = parse_description(row.get("Description", ""))
    base_qty = float(row.get("Qty(+)", 0) or 0)
    parent_item = parent or clean_space(str(row.get("Item", "")))

    # Build component rows
    comp_rows = []
    for tok in tokens:
        item, qty_per = parse_component_token(tok)
        out = row.copy()
        out["Parent_Item"] = parent_item
        out["Item"] = item
        out["Qty_per_parent"] = qty_per
        out["Qty(+)"] = base_qty * qty_per  # multiply
        out["IsParent"] = False
        comp_rows.append(out)

    # Always include the parent row too (helps tracing/diagnostics).
    parent_row = row.copy()
    parent_row["Parent_Item"] = parent_item
    parent_row["Item"] = parent_item
    parent_row["Qty_per_parent"] = 1.0
    parent_row["IsParent"] = True

    if comp_rows:
        return pd.concat([pd.DataFrame(comp_rows), pd.DataFrame([parent_row])],
                         ignore_index=True)
    else:
        # No components in description → only the parent
        return pd.DataFrame([parent_row])

# ---- pipeline --------------------------------------------------------------

def expand_nav_preinstalled(NAV: pd.DataFrame) -> pd.DataFrame:
    NAV = NAV.copy()

    # --- sanity columns ---
    for col in ["Pre/Bare", "Qty(+)", "Item"]:
        if col not in NAV.columns:
            raise ValueError(f"NAV must contain '{col}' column.")
    if "Description" not in NAV.columns:
        NAV["Description"] = ""

    NAV["Description"] = NAV["Description"].astype(str).apply(clean_space)

    # --- split (make copies to avoid SettingWithCopyWarning) ---
    pre_mask = NAV["Pre/Bare"].astype(str).str.strip().str.casefold().eq("pre")
    nav_pre   = NAV.loc[pre_mask].copy()
    nav_other = NAV.loc[~pre_mask].copy()

    # --- expand all Pre rows ---
    expanded_parts = [expand_preinstalled_row(r) for _, r in nav_pre.iterrows()]
    expanded_pre = (
        pd.concat(expanded_parts, ignore_index=True)
        if expanded_parts else nav_pre.copy()
    )

    # --- ensure consistent columns via reindex (no chained assigns) ---
    needed_cols = list(NAV.columns) + ["Parent_Item", "Qty_per_parent", "IsParent"]

    expanded_pre = expanded_pre.reindex(columns=needed_cols, fill_value=pd.NA)
    nav_other    = nav_other.reindex(columns=needed_cols, fill_value=pd.NA)

    # --- set natural parent and flags for non-Pre ---
    nav_other.loc[:, "Parent_Item"]     = nav_other["Item"]
    nav_other.loc[:, "Qty_per_parent"]  = 1.0
    nav_other.loc[:, "IsParent"]        = True  # single line is its own parent

    # --- merge back ---
    expanded_all = pd.concat([expanded_pre, nav_other], ignore_index=True)

    # --- enforce dtypes ---
    expanded_all["Qty(+)"]         = pd.to_numeric(expanded_all["Qty(+)"], errors="coerce").fillna(0.0)
    expanded_all["Qty_per_parent"] = pd.to_numeric(expanded_all["Qty_per_parent"], errors="coerce").fillna(1.0)
    expanded_all["IsParent"]       = expanded_all["IsParent"].astype(bool)
    expanded_all["Date"] = pd.to_datetime(expanded_all["Ship Date"], errors="coerce") + pd.Timedelta(days=5)

    return expanded_all


## 2. Ledger
def build_opening_stock(SO: pd.DataFrame) -> pd.DataFrame:
    """
    Build an opening-stock table per Item from SO snapshot columns.
    prefer_wip=True -> use 'On Hand - WIP' if present else 'On Hand'
    """
    src = SO.copy()
    col = "On Hand"
    if col not in src.columns:
        src[col] = 0.0

    # last non-null per item (or max—choice doesn't matter if consistent)
    stock = (
        src[["Item", col]]
        .dropna()
        .drop_duplicates(subset=["Item"], keep="last")
        .rename(columns={col: "Opening"})
    )
    return stock


def build_events(SO: pd.DataFrame, NAV_EXP: pd.DataFrame) -> pd.DataFrame:
    """
    Create a unified event table: IN from NAV_EXP, OUT from SO.
    Priority rule on same day: IN before OUT (so inbound covers same-day demand).
    """
    so = _norm_cols(SO)
    nav = _norm_cols(NAV_EXP)

    inbound = (
        nav.loc[nav["Qty(+)"] > 0, ["Date", "Item", "Qty(+)"]]
        .rename(columns={"Qty(+)": "Delta"})
        .assign(Kind="IN", Source="NAV")
    )

    outbound = (
        so.loc[so["Qty(-)"] > 0, ["Ship Date", "Item", "Qty(-)", "QB Num", "P. O. #", "Name"]]
        .rename(columns={"Ship Date": "Date", "Qty(-)": "Delta"})
        .assign(Kind="OUT", Source="SO")
    )

    # OUT is negative delta
    outbound["Delta"] = -outbound["Delta"]

    # Standardize columns before concat (missing cols become NaN)
    cols = ["Date", "Item", "Delta", "Kind", "Source", "QB Num", "P. O. #", "Name"]
    inbound  = inbound.reindex(columns=cols)
    outbound = outbound.reindex(columns=cols)

    events = pd.concat([inbound, outbound], ignore_index=True)
    # tie-breaker: IN before OUT on same date
    kind_order = {"IN": 0, "OUT": 1}
    events["kord"] = events["Kind"].map(kind_order).fillna(9).astype(int)

    events.sort_values(["Item", "Date", "kord"], inplace=True)
    events.drop(columns="kord", inplace=True)

    return events


def build_ledger(SO: pd.DataFrame, NAV_EXP: pd.DataFrame, prefer_wip=True) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      ledger: per-item time-phased projection
      item_summary: opening, min projected, first shortage date, ok flag
      violations: rows where projection < 0 (first neg per item marked)
    """
    so = _norm_cols(SO)
    nav = _norm_cols(NAV_EXP)

    stock = build_opening_stock(so)  # Item, Opening
    events = build_events(so, nav)                          # unified IN/OUT

    # Seed an "OPEN" row per item (so cumulative starts from Opening)
    open_rows = []
    today = pd.Timestamp.today().normalize()

    for item, opening in stock.itertuples(index=False):
        open_rows.append({
            "Date": today, "Item": item, "Delta": 0.0,
            "Kind": "OPEN", "Source": "Snapshot", "Opening": opening
        })
    open_df = pd.DataFrame(open_rows)

    # Attach Opening to all events for each item
    events = events.merge(stock, on="Item", how="left")
    events["Opening"] = events["Opening"].fillna(0.0)

    ledger = pd.concat([open_df, events], ignore_index=True, sort=False)

    # cumulative projection per item
    ledger["CumDelta"] = ledger.groupby("Item", sort=False)["Delta"].cumsum()
    # Projected NAV = Opening + CumDelta (OPEN row gives the base)
    ledger["Projected_NAV"] = ledger["Opening"] + ledger["CumDelta"]

    # For OUT rows, it’s useful to know before- and after-delta NAV
    ledger["NAV_before"] = np.where(
        ledger["Kind"].eq("OUT"),
        ledger["Projected_NAV"] - ledger["Delta"],  # since Delta negative
        np.nan
    )
    ledger["NAV_after"] = np.where(
        ledger["Kind"].eq("OUT"),
        ledger["Projected_NAV"],
        np.nan
    )

    # Item summary & violations
    item_min = ledger.groupby("Item", as_index=False)["Projected_NAV"].min().rename(columns={"Projected_NAV": "Min_Projected_NAV"})
    first_neg = (
        ledger.loc[ledger["Projected_NAV"] < 0]
        .sort_values(["Item", "Date"])
        .groupby("Item", as_index=False)
        .first()[["Item", "Date", "Projected_NAV"]]
        .rename(columns={"Date": "First_Shortage_Date", "Projected_NAV": "NAV_at_First_Shortage"})
    )

    item_summary = stock.merge(item_min, on="Item", how="outer").merge(first_neg, on="Item", how="left")
    item_summary["OK"] = item_summary["Min_Projected_NAV"].fillna(0) >= 0

    # Full violations table (all negative points)
    violations = ledger.loc[(ledger["Projected_NAV"]< 0) & (ledger['Date'] != '2099-12-31') & (ledger["Date"].notna())].copy()

    # nice ordering
    ledger.sort_values(["Item", "Date", "Kind"], inplace=True)
    item_summary.sort_values(["OK", "Min_Projected_NAV"], ascending=[True, True], inplace=True)

    return ledger, item_summary, violations


def compute_so_readiness(ledger: pd.DataFrame) -> pd.DataFrame:
    """
    Annotate OUT rows with whether they were covered on their Ship Date,
    and if not, the date inventory returns to non-negative (catch-up date).
    """
    out_rows = ledger.loc[ledger["Kind"].eq("OUT")].copy()

    # covered if NAV_before >= demand quantity (i.e., removing Delta wouldn't go negative)
    # equivalently, NAV_after >= 0
    out_rows["Covered_On_Date"] = out_rows["NAV_after"] >= 0

    # For rows not covered, find the next date where Projected_NAV becomes >= 0
    catchup_dates = []
    g = ledger.groupby("Item", sort=False)

    for idx, r in out_rows.loc[~out_rows["Covered_On_Date"]].iterrows():
        item = r["Item"]
        date = r["Date"]
        # find first row for this item on/after this date where Projected_NAV >= 0
        sub = g.get_group(item)
        sub = sub.loc[sub["Date"] >= date].sort_values("Date", kind="mergesort")
        hit = sub.loc[sub["Projected_NAV"] >= 0]
        catchup_dates.append((idx, hit["Date"].iloc[0] if not hit.empty else pd.NaT))

    catchup_map = {idx: dt for idx, dt in catchup_dates}
    out_rows["Covered_By_Date"] = out_rows.index.map(catchup_map).fillna(pd.NaT)

    return out_rows[[
        "Date", "Item", "Delta", "QB Num", "P. O. #", "Name",
        "NAV_before", "NAV_after", "Covered_On_Date", "Covered_By_Date"
    ]].sort_values(["Item", "Date"])
