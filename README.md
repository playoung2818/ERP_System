# QuickBooks Inventory Analytics – Portfolio Project

I rebuilt QuickBooks operational views into a unified analytics pipeline, blending inventory, sales orders, purchase orders, picking signals, and shipping data to drive lead-time decisions and sales order visibility.

## Highlights
- ETL: normalize and join Inventory Status, Open Sales Orders, POD, shipping schedule, Word pick logs, and PDF WO references.
- Metrics: compute WIP (QB Num list) and WIP quantities, On Hand - WIP, structured ERP views, event/ledger timelines, ATP, and Not-assigned SO exports.
- Delivery: publish to Postgres/Supabase and Google Sheets for visualization and downstream reporting.

## Data inputs
- Inventory Status (warehouse snapshot)
- Open Sales Order
- Open Purchase Orders (POD)
- Shipping schedule
- Word pick API (`/api/word-files`) for picked QB Num / WIP
- PDF WO references from Supabase (`pdf_file_log`)

## Run the ETL
- Install deps from `requirements.txt`.
- Configure DB DSN in `db_config.py` (or environment).
- Update file paths in `ERP_System 2.0/config.py`.
- Run `erp.bat` or `python "ERP_System 2.0/etl.py"`.
- Outputs: inventory_status, structured sales orders, POD, shipping, ledger, item summary, ATP, and Not_assigned_SO exports; pushed to DB and Sheets when configured.

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
