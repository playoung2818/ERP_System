from __future__ import annotations
import re, numpy as np, pandas as pd

# ---------- mappings ----------
mappings = {
    'GC-J-A64GB-O-Industrial-Nvidia': 'GC-Jetson-AGX64GB-Orin-Industrial-Nvidia-JetPack-6.0',
    'GC-Jetson-AGX64GB-Orin-Nvidia': 'GC-Jetson-AGX64GB-Orin-Nvidia-JetPack-6.0',
    'AccsyBx-Cardholder-10108GC-5080': 'AccsyBx-Cardholder-10108GC-5080_70_70Ti',
    'Cblkit-FP-NRU-230V-AWP_NRU-240S': 'Cblkit-FP-NRU-230V-AWP_NRU-240S-AWP',
    'E-mPCIe-GPS-M800_Mod_40CM': 'Extnd-mPCIeHS_GPS-M800_Mod_Cbl-40CM_kits',
    'Cbl-M12A5F-OT2-B-Red-Fuse-100CM': 'Cbl-M12A5F-OT2-Black-Red-Fuse-100CM',
    'AccsyBx-Cardholder-9160GC-2000E': 'AccsyBx-Cardholder-9160GC-2000EAda',
    'M.280-SSD-4TB-PCIe4-TLCWT5NH-IK': 'M.280-SSD-4TB-PCIe4-TLCWT5-NH-IK',
    'M.242-SSD-128GB-PCIe34-TLC5WT-T': 'M.242-SSD-128GB-PCIe34-TLC5WT-TD',
    'M.242-SSD-256GB-PCIe34-TLC5WT-T': 'M.242-SSD-256GB-PCIe34-TLC5WT-TD',
    'M.280-SSD-256GB-PCIe44-TLC5WT-T': 'M.280-SSD-256GB-PCIe44-TLC5WT-TD',
    'M.280-SSD-512GB-PCIe44-TLC5WT-T': 'M.280-SSD-512GB-PCIe44-TLC5WT-TD',
    'E-mPCIe-BTWifi-WT-6218_Mod_40CM': 'Extnd-mPCIeHS-BTWifi-WT-6218_Mod_Cbl-40CM_kits',
    'GC-Jetson-NX16G-Orin-Nvidia': 'GC-Jetson-NX16G-Orin-Nvidia-JetPack6.0',
    'FPnl-3Ant-NRU-170-PPC series': 'FPnl-3Ant-NRU-170-PPCseries',
}

# ---------- small utils ----------
def normalize_wo_number(wo: str) -> str:
    m = re.search(r'\b(20\d{6})\b', str(wo))
    return f"SO-{m.group(1)}" if m else str(wo)

def _norm_dash_series(s: pd.Series) -> pd.Series:
    return s.str.replace(r"[\u2012\u2013\u2014\u2212]", "-", regex=True)

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

# ---------- transform_* (paste your existing ones, lightly adjusted to import mappings) ----------
# --------------------
# Transform 
# --------------------
def transform_sales_order(df_sales_order: pd.DataFrame) -> pd.DataFrame:
    df = df_sales_order.copy()
    df = df.drop(columns = ['Qty', 'Item'])
    df = df.rename(columns={"Unnamed: 0": "Item", "Num": "QB Num", "Backordered": "Qty(-)", "Date":"Order Date"})
    df["Item"] = df["Item"].ffill().astype(str).str.strip()
    df = df[~df["Item"].str.startswith("total", na=False)]
    df = df[~df["Item"].str.lower().isin(["forwarding charge", "tariff (estimation)"])]
    df = df[df["Inventory Site"] == "WH01S-NTA"]
    df['Item'] = df['Item'].replace(mappings)
    return df

def transform_inventory(inventory_df: pd.DataFrame) -> pd.DataFrame:
    inv = inventory_df.copy()
    # only rename ONCE
    inv = inv.rename(columns={"Unnamed: 0":"Part_Number"})
    inv["Part_Number"] = inv["Part_Number"].astype(str).str.strip()
    inv['Part_Number'] = inv['Part_Number'].replace(mappings)
    # make numeric safely
    for c in ["On Hand","On Sales Order","On PO","Available"]:
        if c in inv.columns:
            inv[c] = pd.to_numeric(inv[c], errors="coerce").fillna(0)
    return inv

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
    pod['Item'] = pod['Item'].replace(mappings)
    df_pod = pd.DataFrame(pod)
    return df_pod


def transform_shipping(df_shipping_schedule: pd.DataFrame) -> pd.DataFrame:

    df = df_shipping_schedule.copy()

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

    # coerce Ship Date to yyyy/mm/dd string if you want it normalized (optional)
    Ship["Ship Date"] = pd.to_datetime(Ship["Ship Date"], errors="coerce").dt.date

    # Qty(+) numeric
    Ship["Qty(+)"] = pd.to_numeric(Ship["Qty(+)"], errors="coerce").fillna(0).astype(int)

    # --- Pre/Bare logic ---
    model_ok = Ship["Item"].str.upper().str.startswith(("N", "SEMIL", "POC"), na=False)
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

    # Build df_out from Sales Order (standardize to these final names)
    needed_cols = {
        "Order Date": "SO Entry Date",
        "Name": "Customer",
        "P. O. #": "Customer PO",
        "QB Num": "QB Num",
        "Item": "Item",                # <- part key
        "Qty(-)": "Qty",               # <- create Qty from Backordered/Qty(-)
        "Ship Date": "Lead Time"       # <- keep the name used later
    }
    for src in list(needed_cols.keys()):
        if src not in df_sales_order.columns:
            df_sales_order[src] = "" if src not in ("Qty(-)",) else 0

    df_out = df_sales_order.rename(columns=needed_cols)[list(needed_cols.values())].copy()

    # Keep an auxiliary WO column if source has it (for 'Picked' merge fallback)
    for alt in ["WO", "WO_Number", "NTA Order ID", "SO Number"]:
        if alt in df_sales_order.columns:
            df_out["WO"] = df_sales_order[alt].astype(str).apply(normalize_wo_number)
            break
    if "WO" not in df_out.columns:
        df_out["WO"] = ""

    # Sort to group visually
    df_out = df_out.sort_values(['QB Num', 'Item']).reset_index(drop=True)

    # Rename the PDF reference to match our new keys
    pdf_ref = pdf_orders_df.rename(columns={'WO': 'QB Num', 'Product Number': 'Item'})
    final_sales_order = reorder_df_out_by_output(pdf_ref, df_out)

    # Map the short->long part names
    final_sales_order['Item'] = final_sales_order['Item'].replace(mappings)
    final_sales_order = final_sales_order.loc[:, ~final_sales_order.columns.duplicated()]


    # Merge “Picked” status (collapse per order key)
    word_pick = word_files_df.copy()
    key_used = None

    if "QB Num" in word_pick.columns:
        key_used = "QB Num"
    elif "WO_Number" in word_pick.columns:
        key_used = "WO_Number"
        # normalize to SO-######## format
        word_pick["WO_Number"] = word_pick["WO_Number"].astype(str).apply(normalize_wo_number)

    word_pick["Picked"] = word_pick["status"].astype(str).str.strip().eq("Picked")
    word_pick = word_pick.groupby(key_used, as_index=False)["Picked"].max() if key_used else pd.DataFrame(columns=["WO","Picked"])

    if key_used == "QB Num":
        df_Order_Picked = final_sales_order.merge(word_pick, on="QB Num", how="left")
    elif key_used == "WO_Number":
        df_Order_Picked = final_sales_order.merge(word_pick, left_on="QB Num", right_on="WO_Number", how="left").drop(columns=["WO_Number"])
    else:
        df_Order_Picked = final_sales_order.copy()
        df_Order_Picked["Picked"] = False

    df_Order_Picked["Picked"] = df_Order_Picked["Picked"].map({True: "Picked", False: "No"}).fillna("No")


    # Picked qty per part
    picked_parts = (
        df_Order_Picked.loc[df_Order_Picked["Picked"].eq("Picked")]
        .groupby("Item", as_index=False)["Qty"].sum()
        .rename(columns={"Item": "Part_Number", "Qty": "Picked_Qty"})
    )

    # Inventory merge
    inv_plus = inventory_df.merge(picked_parts, on="Part_Number", how="left")
    for c in ["On Hand", "On Sales Order", "On PO", "Picked_Qty"]:
        if c in inv_plus.columns:
            inv_plus[c] = pd.to_numeric(inv_plus[c], errors="coerce").fillna(0)

    structured_df = df_Order_Picked.merge(
        inv_plus, how="left", left_on="Item", right_on="Part_Number"
    )
    structured_df["Qty"] = pd.to_numeric(structured_df["Qty"], errors="coerce")
    structured_df = structured_df.dropna(subset=["Qty"])

    # Lead Time + assigned totals per Item
    structured_df["Lead Time"] = pd.to_datetime(structured_df["Lead Time"], errors="coerce").dt.floor("D")
    # Convert to datetime first (already in your code)
    structured_df["Lead Time"] = pd.to_datetime(structured_df["Lead Time"], errors="coerce").dt.floor("D")

    # --- Fix dummy dates: move them to 2099 equivalents ---
    mask_july4  = (structured_df["Lead Time"].dt.month.eq(7))  & (structured_df["Lead Time"].dt.day.eq(4))
    mask_dec31  = (structured_df["Lead Time"].dt.month.eq(12)) & (structured_df["Lead Time"].dt.day.eq(31))

    structured_df.loc[mask_july4, "Lead Time"] = pd.Timestamp("2099-07-04")
    structured_df.loc[mask_dec31, "Lead Time"] = pd.Timestamp("2099-12-31")
    assigned_mask = ~(
        (structured_df["Lead Time"].dt.month.eq(7)  & structured_df["Lead Time"].dt.day.eq(4)) |
        (structured_df["Lead Time"].dt.month.eq(12) & structured_df["Lead Time"].dt.day.eq(31))
    )
    assigned_total = structured_df["Qty"].where(assigned_mask, 0).groupby(structured_df["Item"]).transform("sum")
    structured_df["Assigned Q'ty"] = assigned_total
    structured_df["On Hand - WIP"] = structured_df["On Hand"] - structured_df.get("Picked_Qty", 0)


    # Filter pods that have been locked to SO  
    # ['Name'] represents the Customer, ['Source Name'] represents the Vendor
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
    'PhyTools',
    'Mouser Electronics',
    'Genoedge Corporation DBA SabrePC.COM',
    'CoastIPC, Inc.',
    'Industrial PC, Inc.',

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
    structured_df['Pre-installed PO'] = structured_df['Item'].map(lookup).fillna(0)
    structured_df["Available + Pre-installed PO"] = structured_df["Available"] + structured_df['Pre-installed PO']

    ## Recommend Restocking QTY
    # Ensure numeric types and fill NaNs
    structured_df['Reorder Pt (Min)'] = pd.to_numeric(structured_df['Reorder Pt (Min)'], errors='coerce').fillna(0)
    structured_df['Available'] = pd.to_numeric(structured_df['Available'], errors='coerce').fillna(0)
    structured_df['On PO'] = pd.to_numeric(structured_df['On PO'], errors='coerce').fillna(0)

    structured_df['Available + On PO'] = structured_df['Available'] + structured_df['On PO']

    # Calculate Restock Qty
    structured_df['Recommended Restock Qty'] = np.ceil(
    np.maximum(0, (4 * structured_df['Sales/Week']) - structured_df['Available'] - structured_df['On PO'])
).astype(int)

    ## Define Component Status
    structured_df["Component_Status"] = np.where((structured_df["Available + Pre-installed PO"] >= 0) & (structured_df["On Hand"] > 0), "Available", "Shortage") #Available or Shortage   
    structured_df["Qty(+)"] = "0"
    structured_df['Pre/Bare'] = "Out"

    structured_df.rename(columns={"SO Entry Date":"Order Date", "Customer": "Name", "Lead Time": "Ship Date", "Customer PO": "P. O. #", "Qty": "Qty(-)", "SO Status": "SO_Status" },inplace=True)
    for col in ["Order Date", "Ship Date"]:
        structured_df[col] = pd.to_datetime(structured_df[col], errors="coerce").dt.date

    return structured_df, final_sales_order
