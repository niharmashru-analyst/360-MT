import os

# Use either local Excel paths or downloadable OneDrive URLs.
# Leave a value blank if the dataset is not available yet.
DATA_SOURCES = {
    "PRIMARY": os.getenv("PRIMARY_URL", "data/primary.xlsx"),
    "TERTIARY": os.getenv("TERTIARY_URL", "data/tertiary.xlsx"),
    "OP_STOCK": os.getenv("OP_STOCK_URL", "data/op_stock.xlsx"),
    "CL_STOCK": os.getenv("CL_STOCK_URL", "data/cl_stock.xlsx"),
    "DISTRIBUTION": os.getenv("DISTRIBUTION_URL", "data/distribution.xlsx"),
    "TARGET": os.getenv("TARGET_URL", "data/target.xlsx"),
    "OUTLET_MASTER": os.getenv("OUTLET_MASTER_URL", "data/outlet_master.xlsx"),
    "SKU_MASTER": os.getenv("SKU_MASTER_URL", "data/sku_master.xlsx"),
}

# Dashboard refresh cache in minutes.
CACHE_MINUTES = int(os.getenv("CACHE_MINUTES", "15"))

APP_NAME = "MT 360"
APP_SUBTITLE = "Modern Trade Intelligence"
