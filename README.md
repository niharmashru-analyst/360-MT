# MT 360 FINAL
Modern Trade 360 dashboard for a cosmetics business.

Pages:
- Executive Overview
- Sales Performance
- Retailer 360
- Product & Category
- Stock Health
- Distribution
- Target & Margin
- Primary -> Tertiary Flow
- Leakage & Opportunities
- Action Center
- MT Analyst
- Data Health

Dummy Excel files are included in /data. Replace their rows with actual data on Monday.
Keep headers and keys consistent.

Render:
Build: pip install -r requirements.txt
Start: gunicorn app:app --workers 2 --threads 4 --timeout 180

For OneDrive, set these Render environment variables to direct downloadable Excel URLs:
PRIMARY_URL
TERTIARY_URL
OP_STOCK_URL
CL_STOCK_URL
DISTRIBUTION_URL
TARGET_URL
OUTLET_MASTER_URL
SKU_MASTER_URL
