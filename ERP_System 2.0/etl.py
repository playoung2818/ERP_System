import logging
from config import DATABASE_DSN, DB_SCHEMA, TBL_INVENTORY, TBL_STRUCTURED, TBL_SALES_ORDER, TBL_POD, TBL_Shipping, TBL_LEDGER, TBL_ITEM_SUMMARY
from io_ops import (
    extract_inputs, write_to_db, write_final_sales_order_to_gsheet,
    save_not_assigned_so, fetch_word_files_df, fetch_pdf_orders_df_from_supabase
)
from core import (
    transform_sales_order, transform_inventory, transform_pod, transform_shipping,
    build_structured_df, prepare_erp_view, add_onhand_minus_wip
)
from ledger import build_ledger, expand_nav_preinstalled
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def main():
    # Extract
    so_raw, inv_raw, ship_raw, pod_raw = extract_inputs()
    word_files_df = fetch_word_files_df("http://192.168.60.133:5001/api/word-files")
    pdf_orders_df = fetch_pdf_orders_df_from_supabase(DATABASE_DSN)

    # Transform
    so_full = transform_sales_order(so_raw)
    inv     = transform_inventory(inv_raw)
    pod     = transform_pod(pod_raw)
    ship    = transform_shipping(ship_raw)

    # Structured output
    structured, final_sales_order = build_structured_df(so_full, word_files_df, inv, pdf_orders_df, pod)

    # Add "On Hand - WIP" efficiently (vectorized)
    inv = add_onhand_minus_wip(inv, structured)

    # Ledger analytics (optional)
    nav_exp = expand_nav_preinstalled(ship)
    ledger, item_summary, violations = build_ledger(structured, nav_exp, prefer_wip=True)
    print(violations)


    # Not assigned SO
    ERP_df = prepare_erp_view(structured)
    Not_assigned_SO = ERP_df.loc[~ERP_df["AssignedFlag"]].copy()

    # Save Not_assigned_SO.xlsx (reuse your existing logic)
    summary = save_not_assigned_so(
        Not_assigned_SO.copy(),
        output_path= r"C:\Users\Admin\OneDrive - neousys-tech\Desktop\Python\ERP_System\Not_assigned_SO.xlsx",
        highlight_cols="Recommended Restock Qty",
        band_by_col="QB Num",
        shortage_col="Component_Status",
        shortage_value="Shortage",
    )
    print(summary)

    # Load to DB
    write_to_db(inv, schema=DB_SCHEMA, table=TBL_INVENTORY)
    write_to_db(so_full, schema=DB_SCHEMA, table=TBL_SALES_ORDER)
    write_to_db(structured, schema=DB_SCHEMA, table=TBL_STRUCTURED)
    write_to_db(pod, schema=DB_SCHEMA, table=TBL_POD)
    write_to_db(ship, schema=DB_SCHEMA, table=TBL_Shipping)
    write_to_db(ledger, schema=DB_SCHEMA, table=TBL_LEDGER)
    write_to_db(item_summary, schema=DB_SCHEMA, table=TBL_ITEM_SUMMARY)
    print(f"✅ Loaded:{DB_SCHEMA}.{TBL_SALES_ORDER} rows={len(so_full)}; {DB_SCHEMA}.{TBL_INVENTORY} rows={len(inv)}; {DB_SCHEMA}.{TBL_STRUCTURED} rows={len(structured)}; {DB_SCHEMA}.{TBL_POD} rows={len(pod)}; {DB_SCHEMA}.{TBL_Shipping} rows={len(ship)}")

    # Push to Google Sheets
    if not final_sales_order.empty:
        write_final_sales_order_to_gsheet(final_sales_order.assign(
            **{"Lead Time": pd.to_datetime(final_sales_order["Lead Time"], errors="coerce").dt.date}
        ))

if __name__ == "__main__":
    logging.info("Running ETL pipeline...")
    main()
    logging.info("Done.")
