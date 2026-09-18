import io
import os
import re
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from config import DATA_SOURCES, CACHE_MINUTES

_cache = {"ts": 0, "data": None}


def normalize_col(x):
    x = str(x).strip().lower()
    x = re.sub(r"[%₹$]", " ", x)
    x = re.sub(r"[^a-z0-9]+", " ", x)
    return re.sub(r"\s+", " ", x).strip()


ALIASES = {
    "month": ["month", "month year", "monthyear", "date", "period"],
    "outlet_code": ["outlet code", "store code", "store id", "outlet id"],
    "outlet_name": ["outlet name", "store name", "outlet", "store"],
    "chain_name": ["chain name", "chain", "retailer", "retailer name"],
    "chain_type": ["chain type", "format", "channel type", "store type"],
    "location": ["location", "city state region", "place"],
    "city": ["city"],
    "state": ["state"],
    "region": ["region", "zone"],
    "sku": ["sku", "product name", "product"],
    "sku_code": ["sku code", "sku id", "product code", "ean", "ean code"],
    "brand": ["brand", "brand name"],
    "category": ["category"],
    "sub_category": ["sub category", "subcategory", "sub-category"],
    "pareto": ["pareto", "pareto group"],
    "status": ["status", "sku status"],
    "sales_qty": ["sales qty", "sales quantity", "tertiary sales qty", "qty"],
    "sales_value": ["sales value", "sales", "net sales", "sales amount"],
    "mrp": ["mrp", "mrp value", "price"],
    "stock_qty": ["stock qty", "stock quantity", "stock"],
    "target": ["targets", "target", "sales target"],
    "margin_pct": ["margins", "margin", "margin %", "margin pct"],
    "promo_pct": ["promos%", "promo %", "promo pct", "promotion %"],
    "distribution": ["distribution", "listed", "availability", "distributed"],
    "returns": ["returns", "return qty", "sales returns"],
    "store_status": ["store status", "outlet status"],
    "store_format": ["store format", "format"],
    "store_area": ["store area", "area", "sq ft", "sqft"],
}


def standardize(df):
    df = df.copy()
    df.columns = [normalize_col(c) for c in df.columns]
    reverse = {}
    for canonical, variants in ALIASES.items():
        for v in variants:
            reverse[normalize_col(v)] = canonical
    rename = {}
    for c in df.columns:
        if c in reverse:
            rename[c] = reverse[c]
    df = df.rename(columns=rename)

    # If "location" contains city/state/region in one field, preserve it.
    for c in ["sales_qty", "sales_value", "mrp", "stock_qty", "target", "margin_pct", "promo_pct", "returns", "distribution"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    if "month" in df.columns:
        dt = pd.to_datetime(df["month"], errors="coerce")
        # Handle Excel month numbers only when there is no usable date.
        if dt.notna().sum() == 0:
            nums = pd.to_numeric(df["month"], errors="coerce")
            if nums.notna().sum() > 0:
                year = pd.Timestamp.today().year
                df["month"] = pd.to_datetime(
                    {"year": year, "month": nums.clip(1, 12), "day": 1},
                    errors="coerce"
                )
            else:
                df["month"] = pd.NaT
        else:
            df["month"] = dt.dt.to_period("M").dt.to_timestamp()

    return df


def read_source(source: str) -> Optional[pd.DataFrame]:
    if not source:
        return None
    try:
        if source.startswith("http://") or source.startswith("https://"):
            r = requests.get(source, timeout=45, allow_redirects=True)
            r.raise_for_status()
            return standardize(pd.read_excel(io.BytesIO(r.content)))
        p = Path(source)
        if not p.exists():
            return None
        return standardize(pd.read_excel(p))
    except Exception as e:
        print(f"[DATA] Could not read {source}: {e}")
        return None


def load_all(force=False):
    now = time.time()
    if not force and _cache["data"] is not None and now - _cache["ts"] < CACHE_MINUTES * 60:
        return _cache["data"]

    result = {}
    for key, source in DATA_SOURCES.items():
        result[key] = read_source(source)

    # Main analytical table: prefer tertiary sales, but retain primary if available.
    sales = result.get("TERTIARY")
    if sales is None:
        sales = result.get("PRIMARY")
    if sales is None:
        sales = pd.DataFrame()

    # Merge masters when keys are present.
    if result.get("SKU_MASTER") is not None and not sales.empty and "sku_code" in sales.columns:
        sm = result["SKU_MASTER"].drop_duplicates("sku_code")
        extra = [c for c in ["brand", "category", "sub_category"] if c in sm.columns and c not in sales.columns]
        if extra:
            sales = sales.merge(sm[["sku_code"] + extra], on="sku_code", how="left")

    if result.get("OUTLET_MASTER") is not None and not sales.empty and "outlet_code" in sales.columns:
        om = result["OUTLET_MASTER"].drop_duplicates("outlet_code")
        extra = [c for c in ["city", "state", "region", "store_status", "store_format", "store_area"]
                 if c in om.columns and c not in sales.columns]
        if extra:
            sales = sales.merge(om[["outlet_code"] + extra], on="outlet_code", how="left")

    result["SALES"] = sales
    _cache["data"] = result
    _cache["ts"] = now
    return result
