from __future__ import annotations
import re, numpy as np, pandas as pd
from erp_normalize import normalize_item

# ---------- small utils ----------
def normalize_wo_number(wo: str) -> str:
    """
    Normalize a Work Order number by extracting the 8-digit number starting with year (e.g. "SO-20250975")
    and returning it in the format "SO-<year><number>".
    """
    m = re.search(r'\b(20\d{6})\b', str(wo))
    return f"SO-{m.group(1)}" if m else str(wo)


def enforce_column_order(df: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    front = [c for c in order if c in df.columns]
    back  = [c for c in df.columns if c not in front]
    return df.loc[:, front + back]

# ---------- normalization ----------
def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ("Ship Date","Order Date","Arrive Date","Date"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    if "Item" in df.columns:
        df["Item"] = df["Item"].astype(str).str.strip()
    for c in ("Qty(+)","Qty(-)","On Hand","On Hand - WIP","Available","On Sales Order","On PO"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df

# --------------------
# Transform 
# --------------------
def transform_sales_order(df_sales_order: pd.DataFrame) -> pd.DataFrame:
    df = df_sales_order.copy()
    df["partial"] = df["Qty"] != df["Backordered"]
    df = df.drop(columns = ['Qty', 'Item'])
    df = df.rename(columns={"Unnamed: 0": "Item", "Num": "QB Num", "Backordered": "Qty(-)", "Date":"Order Date"})
    df["Item"] = df["Item"].ffill().astype(str).str.strip()
    df = df[~df["Item"].str.startswith("total", na=False)]
    df = df[~df["Item"].str.lower().isin(["forwarding charge", "tariff (estimation)"])]
    df = df[df["Inventory Site"] == "WH01S-NTA"]
    df["Item"] = df["Item"].map(normalize_item)
    return df

def transform_inventory(inventory_df: pd.DataFrame) -> pd.DataFrame:
    inv = inventory_df.copy()
    inv = inv.rename(columns={"Unnamed: 0":"Part_Number"})
    inv["Part_Number"] = inv["Part_Number"].astype(str).str.strip()
    inv["Part_Number"] = inv["Part_Number"].map(normalize_item)
    # make numeric safely
    for c in ["On Hand","On Sales Order","On PO","Available"]:
        if c in inv.columns:
            inv[c] = pd.to_numeric(inv[c], errors="coerce").fillna(0)
    return inv

def transform_pod(df_pod: pd.DataFrame) -> pd.DataFrame:
    pod = df_pod.drop(columns=['Amount','Open Balance',"Rcv'd","Qty", 'Deliv Date'], axis =1)
    pod.rename(columns={"Date":"Order Date","Num":"QB Num","Backordered":"Qty(+)"},inplace=True)
    pod = pod.drop(pod.columns[[0]], axis =1)
    # pod = pod[pod['Name'] == 'Neousys Technology Incorp.'].copy()
    pod = pod.dropna(axis=0, how='all',subset=None, inplace=False)
    pod = pod.dropna(thresh=5)
    pod['Memo'] = pod['Memo'].str.split(' ',expand=True)[0]
    pod['QB Num'] = pod['QB Num'].str.split('(',expand=True)[0]
    # print(pod['Memo'].str.split('*',expand=True)[0])
    pod['Memo'] = pod['Memo'].str.replace("*","")
    pod.rename(columns={"Memo":"Item"},inplace=True)
    pod['Order Date']= pd.to_datetime(pod['Order Date'])
    pod["Item"] = pod["Item"].map(normalize_item)
    df_pod = pd.DataFrame(pod)
    return df_pod


def transform_shipping(df_shipping_schedule: pd.DataFrame) -> pd.DataFrame:

    df = df_shipping_schedule[df_shipping_schedule['Ship to'] == 'Neousys Technology America, Inc.'].copy()

    # --- make sure the columns exist (create empty ones if missing) ---
    need = ['SO NO.', 'Customer PO No.', 'Model Name', 'Ship Date', 'Qty', 'Description']
    for c in need:
        if c not in df.columns:
            df[c] = np.nan

    # --- select and rename ---
    Ship = df.loc[:, need].copy()
    Ship.rename(columns={
        "Customer PO No.": "QB Num",
        "Model Name": "Item",
        "Qty": "Qty(+)"
    }, inplace=True)

    # --- basic cleaning ---
    # QB Num: strip anything after '('
    Ship["QB Num"] = Ship["QB Num"].astype(str).str.split("(").str[0].str.strip()

    # types
    Ship["Item"] = Ship["Item"].astype(str).str.strip()
    Ship["Description"] = Ship["Description"].astype(str)

    Ship["Ship Date"] = pd.to_datetime(Ship["Ship Date"], errors="coerce")

    # Qty(+) numeric
    Ship["Qty(+)"] = pd.to_numeric(Ship["Qty(+)"], errors="coerce").fillna(0).astype(int)

    # --- Pre/Bare logic ---
    model_ok = (
    Ship["Item"].str.upper().str.startswith(("N", "SEMIL", "POC", "F"), na=False)
    & ~Ship["Item"].str.upper().str.startswith("NRU-52S-NX")
)

    # accept English or Chinese comma: ", including" or "， including"
    including_ok = Ship["Description"].str.contains(r"[，,]\s*including\b", case=False, na=False)

    pre_mask = model_ok & including_ok
    Ship["Pre/Bare"] = np.where(pre_mask, "Pre", "Bare")

    # optional: tidy column order
    desired = ["SO NO.", "QB Num", "Item", "Description", "Ship Date", "Qty(+)", "Pre/Bare"]
    Ship = Ship.reindex(columns=[c for c in desired if c in Ship.columns] +
                               [c for c in Ship.columns if c not in desired])
    
    return Ship

# ---------- reorder helper ----------
def reorder_df_out_by_output(output_df: pd.DataFrame, df_out: pd.DataFrame) -> pd.DataFrame:
    """
    Reorder df_out to match the line ordering found in output_df.
    Both frames are expected to use columns: ['QB Num', 'Item'].
    """
    ref = output_df.copy()
    ref['__pos_out'] = ref.groupby('QB Num').cumcount()              # position within QB Num
    ref['__occ'] = ref.groupby(['QB Num', 'Item']).cumcount()        # occurrence index per (QB Num, Item)
    ref_key = ref[['QB Num', 'Item', '__occ', '__pos_out']]

    tgt = df_out.copy()
    tgt['__occ'] = tgt.groupby(['QB Num', 'Item']).cumcount()

    merged = tgt.merge(ref_key, on=['QB Num', 'Item', '__occ'], how='left')

    merged['__fallback'] = merged.groupby('QB Num').cumcount()
    merged['__pos_out'] = merged['__pos_out'].fillna(np.inf)

    ordered = (
        merged.sort_values(['QB Num', '__pos_out', '__fallback'])
              .drop(columns=['__occ', '__pos_out', '__fallback'])
              .reset_index(drop=True)
    )
    return ordered

# ---------- big builder ----------
def build_structured_df(
    df_sales_order: pd.DataFrame,
    word_files_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    pdf_orders_df: pd.DataFrame,
    df_pod: pd.DataFrame
) -> pd.DataFrame:

    # -----------------------------
    # 1) Standardize Sales Order -> df_out
    # -----------------------------
    needed_cols = {
        "Order Date": "SO Entry Date",
        "Name": "Customer",
        "P. O. #": "Customer PO",
        "QB Num": "QB Num",
        "Item": "Item",                # part key
        "Qty(-)": "Qty",               # demand qty (rename to Qty)
        "Ship Date": "Lead Time"
    }
    for src in list(needed_cols.keys()):
        if src not in df_sales_order.columns:
            df_sales_order[src] = "" if src not in ("Qty(-)",) else 0

    df_out = (
        df_sales_order
        .rename(columns=needed_cols)[list(needed_cols.values())]
        .copy()
    )

    # Normalize WO Number
    df_out["WO"] = ""
    for alt in ["WO", "WO_Number", "NTA Order ID", "SO Number"]:
        if alt in df_sales_order.columns:
            df_out["WO"] = df_sales_order[alt].astype(str).apply(normalize_wo_number)
            break

    df_out = df_out.sort_values(["QB Num", "Item"]).reset_index(drop=True)

    # Align PDF refs (WO->QB Num, Product Number->Item), then reorder df_out by your PDF order
    pdf_ref = pdf_orders_df.rename(columns={"WO": "QB Num", "Product Number": "Item"})
    final_sales_order = reorder_df_out_by_output(pdf_ref, df_out)

    # Map short->long names, drop dup columns if any
    final_sales_order["Item"] = final_sales_order["Item"].map(normalize_item)
    final_sales_order = final_sales_order.loc[:, ~final_sales_order.columns.duplicated()]

    # -----------------------------
    # 2) Merge Pick status from Word files
    #    Step A: baseline Picked/No
    #    Step B: upgrade to Partial when backordered > 0
    # -----------------------------
    word_pick = word_files_df.copy()
    word_pick["WO_Number"] = word_pick["WO_Number"].astype(str).apply(normalize_wo_number)

    word_pick["Picked_Flag"] = word_pick["status"].astype(str).str.strip().eq("Picked")
    word_pick = word_pick.groupby("WO_Number", as_index=False)["Picked_Flag"].max()

    df_Order_Picked = (
        final_sales_order
        .merge(word_pick, left_on="QB Num", right_on="WO_Number", how="left")
        .drop(columns=["WO_Number"])
    )
    df_Order_Picked["Picked_Flag"] = df_Order_Picked["Picked_Flag"].astype("boolean").fillna(False)

    # Build unique (QB Num, Item) → partial mapping (True if ANY line is partial)
    partial_map = (
        df_sales_order
        .groupby(["QB Num", "Item"], as_index=False)["partial"]
        .any()                                    # collapse duplicates
        .rename(columns={"partial": "partial_flag"})
    )

    # Merge into df_Order_Picked on the two keys
    df_Order_Picked = df_Order_Picked.merge(
        partial_map, on=["QB Num", "Item"], how="left"
    )

    # Final boolean column
    df_Order_Picked["partial"] = df_Order_Picked["partial_flag"].fillna(False).astype(bool)
    df_Order_Picked.drop(columns=["partial_flag"], inplace=True)


    # Step A: baseline
    df_Order_Picked["Picked"] = np.where(df_Order_Picked["Picked_Flag"], "Picked", "No")
    # Step B: upgrade picked rows to Partial when partial=True
    mask_partial = df_Order_Picked["Picked_Flag"] & df_Order_Picked["partial"]
    df_Order_Picked.loc[mask_partial, "Picked"] = "Partial"

    # -----------------------------
    # 3) Picked qty per part (count only baseline-picked rows, not partial)
    #    If you want partial to still reserve qty, change == "Picked" to .isin(["Picked","Partial"])
    # -----------------------------
    picked_parts = (
        df_Order_Picked.loc[df_Order_Picked["Picked"].eq("Picked")]
        .groupby("Item", as_index=False)["Qty"].sum()
        .rename(columns={"Item": "Part_Number", "Qty": "Picked_Qty"})
    )

    # -----------------------------
    # 4) Merge Inventory
    # -----------------------------
    inv_plus = inventory_df.merge(picked_parts, on="Part_Number", how="left")
    for c in ["On Hand", "On Sales Order", "On PO", "Picked_Qty", "Reorder Pt (Min)", "Sales/Week", "Available"]:
        if c in inv_plus.columns:
            inv_plus[c] = pd.to_numeric(inv_plus[c], errors="coerce").fillna(0)

    structured_df = df_Order_Picked.merge(
        inv_plus, how="left", left_on="Item", right_on="Part_Number"
    )

    # demand qty numeric; drop rows with NaN demand
    structured_df["Qty"] = pd.to_numeric(structured_df["Qty"], errors="coerce")
    structured_df = structured_df.dropna(subset=["Qty"])

    # -----------------------------
    # 5) Lead Time normalization + dummy-date handling
    # -----------------------------
    structured_df["Lead Time"] = pd.to_datetime(structured_df["Lead Time"], errors="coerce").dt.floor("D")

    mask_july4 = (structured_df["Lead Time"].dt.month.eq(7)) & (structured_df["Lead Time"].dt.day.eq(4))
    mask_dec31 = (structured_df["Lead Time"].dt.month.eq(12)) & (structured_df["Lead Time"].dt.day.eq(31))
    structured_df.loc[mask_july4, "Lead Time"] = pd.Timestamp("2099-07-04")
    structured_df.loc[mask_dec31, "Lead Time"] = pd.Timestamp("2099-12-31")

    # Assigned totals per Item (exclude dummy dates)
    not_dummy = ~(
        (structured_df["Lead Time"] == pd.Timestamp("2099-07-04")) |
        (structured_df["Lead Time"] == pd.Timestamp("2099-12-31"))
    )
    structured_df["Assigned Q'ty"] = structured_df["Qty"].where(not_dummy, 0).groupby(structured_df["Item"]).transform("sum")

    # Keep stock sane; reserve only baseline-picked qty; never go negative
    structured_df["Picked_Qty"] = pd.to_numeric(structured_df.get("Picked_Qty", 0), errors="coerce").fillna(0)
    structured_df["On Hand"] = pd.to_numeric(structured_df.get("On Hand", 0), errors="coerce").fillna(0)
    structured_df["On Hand - WIP"] = (structured_df["On Hand"] - structured_df["Picked_Qty"]).clip(lower=0)

    # -----------------------------
    # 6) Vendor PO filtering -> Pre-installed PO
    # -----------------------------
    filtered = df_pod[~df_pod["Name"].isin([
        "Neousys Technology Incorp.",
        "Amazon", "Newegg Business, Inc.", "Newegg.com",
        "Kontron America, Inc.", "Provantage LLC",
        "SMART Modular Technologies, Inc.", "Spectrum Sourcing",
        "Arrow Electronics, Inc.", "ASI Computer Technologies, Inc.",
        "B&H", "PhyTools", "Mouser Electronics",
        "Genoedge Corporation DBA SabrePC.COM",
        "CoastIPC, Inc.", "Industrial PC, Inc."
    ])]
    result = filtered.groupby("Item", as_index=False)["Qty(+)"].sum()
    lookup = (
        result[["Item", "Qty(+)"]]
        .drop_duplicates(subset=["Item"])
        .set_index("Item")["Qty(+)"]
    )
    structured_df["Pre-installed PO"] = structured_df["Item"].map(lookup).fillna(0)

    # -----------------------------
    # 7) Availability + Restock + Component Status
    # -----------------------------
    structured_df["Available"] = pd.to_numeric(structured_df.get("Available", 0), errors="coerce").fillna(0)
    structured_df["On PO"] = pd.to_numeric(structured_df.get("On PO", 0), errors="coerce").fillna(0)
    structured_df["Reorder Pt (Min)"] = pd.to_numeric(structured_df.get("Reorder Pt (Min)", 0), errors="coerce").fillna(0)
    structured_df["Sales/Week"] = pd.to_numeric(structured_df.get("Sales/Week", 0), errors="coerce").fillna(0)

    structured_df["Available + Pre-installed PO"] = structured_df["Available"] + structured_df["Pre-installed PO"]
    structured_df["Available + On PO"] = structured_df["Available"] + structured_df["On PO"]

    structured_df["Recommended Restock Qty"] = np.ceil(
        np.maximum(0, (4 * structured_df["Sales/Week"]) - structured_df["Available"] - structured_df["On PO"])
    ).astype(int)

    structured_df["Component_Status"] = np.select(
        [
            (structured_df["Available"] >= 0) & (structured_df["On Hand"] > 0),
            (structured_df["Available"] + structured_df["On PO"] > 0)
        ],
        ["Available", "Waiting"],
        default="Shortage"
    )

    # -----------------------------
    # 8) Final column polish
    # -----------------------------
    structured_df["Qty(+)"] = "0"
    structured_df["Pre/Bare"] = "Out"

    structured_df.rename(
        columns={
            "SO Entry Date": "Order Date",
            "Customer": "Name",
            "Lead Time": "Ship Date",
            "Customer PO": "P. O. #",
            "Qty": "Qty(-)",
            "SO Status": "SO_Status"
        },
        inplace=True
    )

    for col in ["Order Date", "Ship Date"]:
        if col in structured_df.columns:
            structured_df[col] = pd.to_datetime(structured_df[col], errors="coerce").dt.strftime("%m/%d/%Y")

    return structured_df, final_sales_order



#  Create Dataframe for LT assignment purpose
def prepare_erp_view(structured: pd.DataFrame) -> pd.DataFrame:
    """
    Selects key ERP columns, ensures 'Ship Date' is datetime,
    and flags 'Not_assigned_SO' based on placeholder dates (7/4, 12/31).
    """
    # --- select necessary columns ---
    cols = [
        'Order Date', 'Name', 'QB Num', 'Item', 'Qty(-)',
        'Available', 'Available + On PO', 'Sales/Week','Recommended Restock Qty', 
        'Available + Pre-installed PO', 'On Hand - WIP', "Assigned Q'ty", 
        'On Hand', 'On Sales Order', 'On PO', 'Component_Status', 'P. O. #', 'Ship Date'
    ]
    df = structured.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    ERP_df = df[cols].copy()

    # --- make sure Ship Date is datetime ---
    ERP_df["Ship Date"] = pd.to_datetime(ERP_df["Ship Date"], errors="coerce")

    # --- flag “not assigned” SOs (using 7/4 or 12/31 placeholders) ---
    mask = (
        (ERP_df["Ship Date"].dt.month.eq(7)  & ERP_df["Ship Date"].dt.day.eq(4)) |
        (ERP_df["Ship Date"].dt.month.eq(12) & ERP_df["Ship Date"].dt.day.eq(31))
    )

    ERP_df["AssignedFlag"] = ~mask  # True = valid Ship Date, False = placeholder

    ERP_df["Ship Date"] = ERP_df["Ship Date"].dt.strftime("%m/%d/%Y")

    return ERP_df


def _norm_key(s: pd.Series) -> pd.Series:
    # robust, null-safe, dtype-safe key normalizer
    s = s.astype("string")              # pandas StringDtype, keeps <NA>
    s = s.str.strip().str.upper()
    return s

def add_onhand_minus_wip(inv: pd.DataFrame, structured: pd.DataFrame) -> pd.DataFrame:
    out = inv.copy()

    # Ensure needed columns exist and are numeric
    if "On Hand" not in out.columns:
        out["On Hand"] = 0
    out["On Hand"] = pd.to_numeric(out["On Hand"], errors="coerce").fillna(0.0)

    # --- normalize join key 'Item' on BOTH dataframes ---
    out["__ITEM_KEY__"] = _norm_key(out.get("Item", pd.Series(pd.NA, index=out.index)))
    st = structured.copy()
    st["__ITEM_KEY__"] = _norm_key(st.get("Item", pd.Series(pd.NA, index=st.index)))

    # Compute WIP from structured (sum of Assigned Q'ty per normalized item)
    if "Assigned Q'ty" in st.columns:
        st["Assigned Q'ty"] = pd.to_numeric(st["Assigned Q'ty"], errors="coerce").fillna(0.0)
        wip = (
            st.loc[st["Assigned Q'ty"].ne(0), ["__ITEM_KEY__", "Assigned Q'ty"]]
              .groupby("__ITEM_KEY__", as_index=False)["Assigned Q'ty"].sum()
              .rename(columns={"Assigned Q'ty": "WIP"})
        )
    else:
        wip = pd.DataFrame({"__ITEM_KEY__": out["__ITEM_KEY__"].unique(), "WIP": 0.0})

    # Merge on the normalized key (both are StringDtype now)
    out = out.merge(wip, on="__ITEM_KEY__", how="left")
    out["WIP"] = out["WIP"].fillna(0.0)

    # Derive 'On Hand - WIP'
    out["On Hand - WIP"] = out["On Hand"] - out["WIP"]

    # Clean up helper column
    out.drop(columns=["__ITEM_KEY__"], inplace=True)

    return out
