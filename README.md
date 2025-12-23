# QuickBooks Inventory Visualization (ERP System)

This project rebuilds QuickBooks views for inventory and order management. It combines Inventory Status, Sales Orders, Purchase Orders, pick/pack signals, and shipping data to produce structured analytics and tailored lead-time guidance.

## What it does
- Normalize and merge Inventory Status, Sales Orders, Purchase Orders (POD), shipping schedule, Word pick logs, and PDF WOs.
- Compute WIP and On Hand - WIP, structured ERP views, ledger/events, ATP, and a Not-assigned SO export.
- Push curated outputs to Postgres/Supabase and Google Sheets for downstream visualization.

## Data sources
- `Inventory Status` (warehouse snapshot)
- `Open Sales Order`
- `Open Purchase Orders (POD)`
- `Shipping schedule`
- Word pick API (`/api/word-files`) for picked QB Num / WIP
- PDF order references (Supabase `pdf_file_log`)

## Running the pipeline
- Ensure Python dependencies from `requirements.txt` are installed.
- Set DSN in `db_config.py` (or env var if applicable).
- Update file paths in `ERP_System 2.0/config.py` as needed.
- Run: `erp.bat` (calls `ERP_System 2.0/etl.py`), or execute `python "ERP_System 2.0/etl.py"`.
- Outputs: inventory_status, structured sales orders, POD, shipping, ledger, item summary, ATP, and Not_assigned_SO export; publishes to DB and Google Sheets when configured.

## Lead Time Assignment Workflow
```text
[Receiving WO]
    |
    v
[Check Inventory Status: available > 0 and ATP > 0?]
    |-- Yes -> [Check Labor Hour]
    |           |-- Yes -> [Assign LT]
    |           |-- No  -> [Wait until labor available]
    |
    |-- No  -> [Check if PO for short items exists]
               |-- Yes -> [Assign LT = Vendor Ship Date + 7]
               |-- No  -> [Ask Taipei to place order]
```

## Projected Inventory Shortages
<img width="1691" height="567" alt="image" src="https://github.com/user-attachments/assets/995b4df0-06fe-4c86-86a8-ba2ff2670364" />