# === File paths ===
SALES_ORDER_FILE = r"C:\Users\Admin\OneDrive - neousys-tech\Share NTA Warehouse\Daily Update\Open Sales Order 10_15_2025.CSV"
WAREHOUSE_INV_FILE = r"C:\Users\Admin\OneDrive - neousys-tech\Share NTA Warehouse\Daily Update\WH01S_10_15.CSV"
SHIPPING_SCHEDULE_FILE = r"C:\Users\Admin\OneDrive - neousys-tech\Share NTA Warehouse\Daily Update\NTA_Shipping schedule_20251013.xlsx"
POD_FILE = r"C:\Users\Admin\OneDrive - neousys-tech\Share NTA Warehouse\Daily Update\POD_10_14.CSV"

# === Supabase/Postgres (pooled) ===
# add sslmode=require to avoid TLS errors
DATABASE_DSN = (
    "postgresql://postgres.avcznjglmqhmzqtsrlfg:Czheyuan0227@"
    "aws-0-us-east-2.pooler.supabase.com:6543/postgres?sslmode=require"
)

# === Target tables (pick schema you actually use) ===
DB_SCHEMA = "public"
TBL_INVENTORY = "inventory_status"
TBL_STRUCTURED = "wo_structured"
TBL_SALES_ORDER = "open_sales_orders"
TBL_POD = "Open_Purchase_Orders"
