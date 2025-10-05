import json, re, numpy as np, pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import logging
from flask import Flask, jsonify 
from flask_sqlalchemy import SQLAlchemy 
from config import ( # type: ignore
    SALES_ORDER_FILE, WAREHOUSE_INV_FILE, SHIPPING_SCHEDULE_FILE, POD_FILE,
    DATABASE_DSN, DB_SCHEMA, TBL_INVENTORY, TBL_STRUCTURED, TBL_SALES_ORDER, TBL_POD
)
import logging, sys, traceback
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")

# Some Part Names are too long to show in QB
mappings = {
    'M.280-SSD-256GB-PCIe44-TLC5WT-T': 'M.280-SSD-256GB-PCIe44-TLC5WT-TD',
    'M.280-SSD-512GB-PCIe44-TLC5WT-T': 'M.280-SSD-512GB-PCIe44-TLC5WT-TD',
    'M.242-SSD-256GB-PCIe34-TLC5WT-T': 'M.242-SSD-256GB-PCIe34-TLC5WT-TD',
    'M.242-SSD-512GB-PCIe34-TLC5WT-T': 'M.242-SSD-512GB-PCIe34-TLC5WT-TD',
    'M.242-SSD-128GB-PCIe34-TLC5WT-T': 'M.242-SSD-128GB-PCIe34-TLC5WT-TD',
    'Cblkit-FP-NRU-230V-AWP_NRU-240S': 'Cblkit-FP-NRU-230V-AWP_NRU-240S-AWP',
}

# --------------------
# Helpers
# --------------------
def engine():
    return create_engine(DATABASE_DSN, pool_pre_ping=True)

def write_inventory_status(df: pd.DataFrame, schema: str = "public", table: str = "inventory_status"):
    eng = engine()
    df.to_sql(
        table,                 
        eng,
        schema=schema,
        if_exists="replace",   # drops + recreates to match df columns
        index=False,
        method="multi",
        chunksize=10_000,
    )

def write_sales_order(df_sales_order: pd.DataFrame, schema: str = "public", table: str = "sales_order"):
    eng = engine()
    df_sales_order.to_sql(
    table,                 
    eng,
    schema=schema,
    if_exists="replace",   # drops + recreates to match df columns
    index=False,
    method="multi",
    chunksize=10_000,
)

def write_structured(structured_df: pd.DataFrame, schema: str = "public", table: str = "wo_structured"):
    eng = engine()
    structured_df.to_sql(
        table,
        eng,
        schema=schema,
        if_exists="replace",   # drops + recreates to match df
        index=False,
        method="multi",
        chunksize=10_000,
    )

def write_pod(df_pod: pd.DataFrame, schema: str = "public", table: str = "open_purchase_order"):
    eng = engine()
    df_pod.to_sql(
        table,
        eng,
        schema=schema,
        if_exists="replace",   # drops + recreates to match df
        index=False,
        method="multi",
        chunksize=10_000,
    )

def write_final_sales_order_to_gsheet(
    df: pd.DataFrame,
    *,
    spreadsheet_name: str,
    worksheet_name: str,
    cred_path: str,
):
    """
    Overwrites (or creates) the given worksheet and writes df with headers.
    Auto-resizes the sheet to fit df shape.
    """
    # 1) auth
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(cred_path, scope)
    client = gspread.authorize(creds)

    # 2) open spreadsheet (by name) — or use client.open_by_key("<spreadsheet_id>")
    sh = client.open(spreadsheet_name)

    # 3) get/create worksheet
    try:
        ws = sh.worksheet(worksheet_name)
        ws.clear()
    except gspread.exceptions.WorksheetNotFound:
        # at least 100 rows/cols to avoid size errors; we’ll resize next
        ws = sh.add_worksheet(title=worksheet_name, rows=100, cols=26)

    # 4) write
    set_with_dataframe(ws, df, include_index=False, include_column_header=True, resize=True)

    # freeze header row for readability
    try:
        ws.freeze(rows=1)
    except Exception:
        pass

    print(f"✅ Wrote {len(df)} rows to Google Sheet → {spreadsheet_name} / {worksheet_name}")

def normalize_wo_number(wo: str) -> str:
    m = re.search(r'\b(20\d{6})\b', str(wo))
    return f"SO-{m.group(1)}" if m else str(wo)

# --------------------
# Extract
# --------------------
def extract_inputs():
    df_sales_order = pd.read_csv(SALES_ORDER_FILE, encoding="ISO-8859-1")
    inventory_df = pd.read_csv(WAREHOUSE_INV_FILE)
    df_shipping_schedule = pd.read_excel(SHIPPING_SCHEDULE_FILE)
    df_pod = pd.read_csv(POD_FILE, encoding="ISO-8859-1")
    return df_sales_order, inventory_df, df_shipping_schedule, df_pod

def fetch_word_files_df(api_url: str) -> pd.DataFrame:
    import requests
    try:
        r = requests.get(api_url, timeout=10)
        r.raise_for_status()
        data = r.json()
        wf = pd.DataFrame(data.get("word_files", []))
    except Exception:
        wf = pd.DataFrame(columns=["file_name","order_id","status"])
    if "order_id" in wf.columns:
        wf = wf.rename(columns={"order_id":"WO_Number"})
    wf["WO_Number"] = wf["WO_Number"].astype(str).apply(normalize_wo_number)
    return wf


def fetch_pdf_orders_df_from_supabase(dsn: str) -> pd.DataFrame:
    """
    Reads order_id + extracted_data from public.pdf_file_log and returns a
    two-column DataFrame with ['WO','Product Number'] rows, one per item in JSON.
    """
    eng = create_engine(dsn, pool_pre_ping=True)
    rows = pd.read_sql('SELECT order_id, extracted_data FROM public.pdf_file_log', eng)

    def rows_from_json(extracted_data, order_id=""):
        # extracted_data may be JSON string or dict
        if isinstance(extracted_data, str):
            try:
                extracted_data = json.loads(extracted_data)
            except Exception:
                extracted_data = {}
        data = extracted_data or {}
        wo = data.get("wo", order_id)
        items = data.get("items") or []

        # one row per item; if none, keep a placeholder
        if not items:
            return [{"WO": wo, "Product Number": ""}]
        out = []
        for it in items:
            pn = (
                it.get("product_number")
                or it.get("part_number")
                or it.get("product")
                or it.get("part")
                or ""
            )
            out.append({"WO": wo, "Product Number": pn})
        return out

    all_rows = []
    for _, r in rows.iterrows():
        all_rows.extend(rows_from_json(r.get("extracted_data"), r.get("order_id")))

    return pd.DataFrame(all_rows, columns=["WO", "Product Number"])


# --------------------
# Transform 
# --------------------
def transform_sales_order(df_sales_order: pd.DataFrame) -> pd.DataFrame:
    df = df_sales_order.copy()
    df = df.drop(columns = ['Qty'])
    df = df.rename(columns={"Unnamed: 0": "Component", "Num": "WO_Number", "Backordered": "Qty"})
    df["Component"] = df["Component"].ffill().astype(str).str.strip()
    df = df[~df["Component"].str.startswith("total", na=False)]
    df = df[~df["Component"].str.lower().isin(["forwarding charge", "tariff (estimation)"])]
    df = df[df["Inventory Site"] == "WH01S-NTA"]
    df['Component'] = df['Component'].replace(mappings)
    return df

def transform_inventory(inventory_df: pd.DataFrame) -> pd.DataFrame:
    inv = inventory_df.copy()
    # only rename ONCE
    inv = inv.rename(columns={"Unnamed: 0":"Part_Number", "Available":"Stock_Available"})
    inv["Part_Number"] = inv["Part_Number"].astype(str).str.strip()
    inv['Part_Number'] = inv['Part_Number'].replace(mappings)
    # make numeric safely
    for c in ["On Hand","On Sales Order","On PO","Stock_Available"]:
        if c in inv.columns:
            inv[c] = pd.to_numeric(inv[c], errors="coerce").fillna(0)
    return inv

def reorder_df_out_by_output(output_df: pd.DataFrame, df_out: pd.DataFrame) -> pd.DataFrame:
    # 1) output_df is from PDFs, df_out is from Excel open sales order
    ref = output_df.copy()
    ref['__pos_out'] = ref.groupby('WO').cumcount()                 # position within WO
    ref['__occ'] = ref.groupby(['WO','Product Number']).cumcount()  # occurrence index for duplicates
    ref_key = ref[['WO','Product Number','__occ','__pos_out']]

    # 2) On df_out, tag each duplicate with its own occurrence index
    tgt = df_out.copy()
    tgt['__occ'] = tgt.groupby(['WO','Product Number']).cumcount()

    # 3) Merge positions from output_df to df_out rows (match by WO + Product + occurrence)
    merged = tgt.merge(ref_key, on=['WO','Product Number','__occ'], how='left')

    # 4) For rows not present in output_df, keep their original within-WO order but push them after the matched ones
    merged['__fallback'] = merged.groupby('WO').cumcount()
    merged['__pos_out'] = merged['__pos_out'].fillna(np.inf)

    # 5) Final order: by WO, then by output_df position; if missing, by original order
    ordered = (merged
               .sort_values(['WO','__pos_out','__fallback'])
               .drop(columns=['__occ','__pos_out','__fallback'])
               .reset_index(drop=True))
    return ordered


def extracted_to_df(order):
    """Return a 2‑column DataFrame: ['WO','Product Number'] for one PDFFileLog row."""
    if order is None:
        return pd.DataFrame(columns=["WO", "Product Number"])

    data = order['extracted_data'] or {}
    if isinstance(data, str):              # if stored as TEXT/JSONB string
        try:
            data = json.loads(data)
        except Exception:
            data = {}

    items = data.get("items") or []
    wo = data.get("wo") or getattr(order, "order_id", "")

    rows = [{
        "WO": wo,
        "Product Number": (
            it.get("product_number") or it.get("part_number")
            or it.get("product") or it.get("part") or ""
        ),
    } for it in items]

    if not rows:
        rows = [{"WO": wo, "Product Number": ""}]

    return pd.DataFrame(rows, columns=["WO", "Product Number"])

def _norm_dash_series(s: pd.Series) -> pd.Series:
    # unify fancy dashes to ASCII hyphen
    return s.str.replace(r"[\u2012\u2013\u2014\u2212]", "-", regex=True)

# def normalize_for_match(df: pd.DataFrame) -> pd.DataFrame:
#     """Normalize WO + Product Number for matching (trim, dashes, case)."""
#     out = df.copy()
#     out["WO"] = out["WO"].astype(str).str.strip().apply(normalize_wo_number)
#     out["Product Number"] = (
#         out["Product Number"].astype(str).str.strip().pipe(_norm_dash_series)
#     )
#     return out

def enforce_column_order(df: pd.DataFrame, order: list[str]) -> pd.DataFrame:
    """Reorder columns to `order`, keeping any extras at the end."""
    front = [c for c in order if c in df.columns]
    back  = [c for c in df.columns if c not in front]
    return df.loc[:, front + back]

def transform_pod(df_pod: pd.DataFrame) -> pd.DataFrame:
    pod = df_pod.drop(columns=['Amount','Open Balance',"Rcv'd","Qty"], axis =1)
    pod.rename(columns={"Date":"Order Date","Num":"QB Num","Backordered":"Qty(+)"},inplace=True)
    pod = pod.drop(pod.columns[[0]], axis =1)
    pod = pod.dropna(axis=0, how='all',subset=None, inplace=False)
    pod = pod.dropna(thresh=5)
    pod['Memo'] = pod['Memo'].str.split(' ',expand=True)[0]
    pod['QB Num'] = pod['QB Num'].str.split('(',expand=True)[0]
    # print(pod['Memo'].str.split('*',expand=True)[0])
    pod['Memo'] = pod['Memo'].str.replace("*","")
    pod.rename(columns={"Memo":"Item"},inplace=True)
    pod['Order Date']= pd.to_datetime(pod['Order Date'])
    pod['Deliv Date']= pd.to_datetime(pod['Deliv Date'])
    pod['Order Date'] = pod['Order Date'].dt.strftime('%Y/%m/%d')
    pod['Deliv Date'] = pod['Deliv Date'].dt.strftime('%Y/%m/%d')
    df_pod = pd.DataFrame(pod)
    return df_pod


def build_structured_df(
    df_sales_order: pd.DataFrame,
    word_files_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    pdf_orders_df: pd.DataFrame,
    df_pod: pd.DataFrame
) -> pd.DataFrame:

    # Build df_out from Sales Order 
    needed_cols = {
        "Date": "SO Entry Date",
        "Name": "Customer",
        "P. O. #": "Customer PO",
        "WO_Number": "WO",
        "Component": "Product Number",
        "Backordered": "Qty",
        "Ship Date": "Lead Time"
    }
    for c in ["Customer","PO"]:
        if c not in df_sales_order.columns:
            df_sales_order[c] = ""

    df_out = df_sales_order.rename(columns=needed_cols)[list(needed_cols.values())]

    # Sort to group visually by WO, then by Product Number
    df_out = df_out.sort_values(['WO', 'Product Number']).reset_index(drop=True)

    final_sales_order = reorder_df_out_by_output(pdf_orders_df, df_out)

    final_sales_order['Product Number'] = final_sales_order['Product Number'].replace(mappings)

    final_sales_order = final_sales_order.loc[:, ~final_sales_order.columns.duplicated()]

    # Merge “Picked” status (collapse per WO)
    word_pick = (
        word_files_df.assign(Picked=word_files_df["status"].astype(str).str.strip().eq("Picked"))
        .groupby("WO_Number", as_index=False)["Picked"].max()
    )
    word_pick["Picked"] = word_pick["Picked"].map({True:"Picked", False:"No"})
    df_Order_Picked = (
        final_sales_order
        .merge(word_pick, left_on="WO", right_on="WO_Number", how="left")
        .drop(columns=["WO_Number"])
    )
    df_Order_Picked["Picked"] = df_Order_Picked["Picked"].fillna("No")

    # Picked qty per part
    picked_parts = (
        df_Order_Picked.loc[df_Order_Picked["Picked"].eq("Picked")]
        .groupby("Product Number", as_index=False)["Qty"].sum()
        .rename(columns={"Product Number":"Part_Number","Qty":"Picked_Qty"})
    )

    # Inventory merge
    inv_plus = inventory_df.merge(picked_parts, on="Part_Number", how="left")
    for c in ["On Hand","On Sales Order","On PO","Picked_Qty"]:
        if c in inv_plus.columns:
            inv_plus[c] = pd.to_numeric(inv_plus[c], errors="coerce").fillna(0)

    structured_df = df_Order_Picked.merge(
        inv_plus, how="left", left_on="Product Number", right_on="Part_NumbeR".lower().capitalize() if False else "Part_Number"
    )
    structured_df["Qty"] = pd.to_numeric(structured_df["Qty"], errors="coerce")
    structured_df = structured_df.dropna(subset=["Qty"])

    # ATP(LT)
    structured_df["Lead Time"] = pd.to_datetime(structured_df["Lead Time"], errors="coerce").dt.floor("D")
    assigned_mask = ~(
        (structured_df["Lead Time"].dt.month.eq(7)  & structured_df["Lead Time"].dt.day.eq(4)) |
        (structured_df["Lead Time"].dt.month.eq(12) & structured_df["Lead Time"].dt.day.eq(31))
    )
    assigned_total = structured_df["Qty"].where(assigned_mask, 0).groupby(structured_df["Product Number"]).transform("sum")
    structured_df["ATP(LT)"] = (structured_df["On Hand"] - assigned_total).clip(lower=0)
    structured_df["In Stock(Inventory)"] = structured_df["On Hand"] - structured_df.get("Picked_Qty", 0)

    # Filter pods that have been locked to SO
    filtered = df_pod[~df_pod['Name'].isin([
    'Neousys Technology Incorp.',
    'Amazon',
    'Newegg Business, Inc.',
    'Newegg.com',
    'Kontron America, Inc.',
    'Provantage LLC',
    'SMART Modular Technologies, Inc.',
    'Spectrum Sourcing',
    'Arrow Electronics, Inc.',
    'ASI Computer Technologies, Inc.',
    'B&H',
    'Phytools'

])]
    result = (
        filtered.groupby('Item', as_index=False)['Qty(+)']
        .sum()
    )
    lookup = (
        result[['Item', 'Qty(+)']]
        .drop_duplicates(subset=['Item'])         # ensures uniqueness
        .set_index('Item')['Qty(+)'] # Series: index = part_number
    )
    structured_df['Qty(+)'] = structured_df['Product Number'].map(lookup).fillna(0)
    structured_df["Available + installed PO"] = structured_df["Stock_Available"] + structured_df["Qty(+)"]



    ## Define Component Status
    structured_df["Component_Status"] = np.where((structured_df["Available + installed PO"] >= 0) & (structured_df["On Hand"] >= structured_df["Qty"]), "Available", "Shortage") #Available or Shortage



    return structured_df, final_sales_order



# --------------------
# Runner
# --------------------
def main():
    # 1) Extract inputs
    so_raw, inv_raw, ship, df_pod = extract_inputs()

    # 2) External sources
    word_files_df = fetch_word_files_df("http://192.168.60.133:5001/api/word-files")

    # 3) Transform
    so_full = transform_sales_order(so_raw)   # <-- keep the full frame (with Qty, Lead Time, etc.)
    inv = transform_inventory(inv_raw)
    df_pod = transform_pod(df_pod)

    # 4) PDF orders from Supabase -> two columns ["WO","Product Number"]
    pdf_orders_df = fetch_pdf_orders_df_from_supabase(DATABASE_DSN)

    # 5) Build structured_df
    structured, final_sales_order = build_structured_df(so_full, word_files_df, inv, pdf_orders_df, df_pod)

    
    
    # 6) Load to Supabase
    write_inventory_status(inv, table=TBL_INVENTORY, schema=DB_SCHEMA)
    write_sales_order(so_full, table=TBL_SALES_ORDER, schema=DB_SCHEMA)
    write_structured(structured, table=TBL_STRUCTURED, schema=DB_SCHEMA)
    write_pod(df_pod, table=TBL_POD, schema=DB_SCHEMA)

    print(f"✅ Loaded:{DB_SCHEMA}.{TBL_SALES_ORDER} rows={len(so_full)}; {DB_SCHEMA}.{TBL_INVENTORY} rows={len(inv)}; {DB_SCHEMA}.{TBL_STRUCTURED} rows={len(structured)}; {DB_SCHEMA}.{TBL_POD} rows={len(df_pod)}")


    # 7)Upload final_sales_order to Google Sheets
    if not final_sales_order.empty:
        write_final_sales_order_to_gsheet(
            final_sales_order.assign(**{
                # Optional: make Lead Time a date for the sheet only
                "Lead Time": pd.to_datetime(final_sales_order["Lead Time"], errors="coerce").dt.date
            }),
            spreadsheet_name="PDF_WO",
            worksheet_name="Open Sales Order",
            cred_path=r"C:\Users\Admin\Downloads\pdfwo-466115-734096e1cef8.json",
        )
    else:
        logging.info("No Open Sales Order rows to write to Google Sheets.")


if __name__ == "__main__":
    try:
        logging.info("Running: %s", __file__)
        main()
        logging.info("Done.")
    except Exception as e:
        logging.error("FATAL: %s", e)
        traceback.print_exc()
        sys.exit(1)



# TODO

# Automatically update the Word-files API

# Reuse a single SQLAlchemy engine.

# Add validate= to merges and require_cols() checks.

# Replace np.inf with a large int sentinel for stable sorting.

# Add HTTP retries for the Word-files API.

# Gate external side-effects behind flags/env so local dev never blocks.