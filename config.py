import os
DATA_SOURCES={
"PRIMARY":os.getenv("PRIMARY_URL","data/PRIMARY.xlsx"),
"TERTIARY":os.getenv("TERTIARY_URL","data/TERTIARY.xlsx"),
"OP_STOCK":os.getenv("OP_STOCK_URL","data/OP_STOCK.xlsx"),
"CL_STOCK":os.getenv("CL_STOCK_URL","data/CL_STOCK.xlsx"),
"DISTRIBUTION":os.getenv("DISTRIBUTION_URL","data/DISTRIBUTION.xlsx"),
"TARGET":os.getenv("TARGET_URL","data/TARGET.xlsx"),
"OUTLET_MASTER":os.getenv("OUTLET_MASTER_URL","data/OUTLET_MASTER.xlsx"),
"SKU_MASTER":os.getenv("SKU_MASTER_URL","data/SKU_MASTER.xlsx")}
CACHE_MINUTES=int(os.getenv("CACHE_MINUTES","10"))
