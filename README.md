# MT 360 — Modern Trade Intelligence Dashboard

Flask + Pandas dashboard designed for a cosmetics Modern Trade business.

## Data model
The app supports these logical datasets:
- PRIMARY
- TERTIARY
- OP STOCK
- CL STOCK
- DISTRIBUTION (optional)
- TARGET (optional)
- OUTLET MASTER (optional)
- SKU MASTER (optional)

You can provide them as local Excel files or public OneDrive download URLs.

## Important
For OneDrive, put a direct/downloadable file URL in `config.py`. A normal browser sharing page URL may not work with server-side downloads.

## Expected columns
Core:
Month, Outlet Code, Outlet Name, Chain Name, Location, Chain Type,
SKU, SKU Code, Pareto, Category, Status, Sales Qty, Sales Value,
MRP, Stock Qty, Targets, Margins, Promos%

Recommended:
Brand, Sub Category, City, State, Region, Distribution, Returns,
Store Status, Store Format, Store Area

The loader is intentionally tolerant of naming differences and normalizes headers.

## Run locally
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py

Then open http://127.0.0.1:5000

## Deploy
Push the folder to GitHub and connect the repository to Render.
