import pandas as pd
import numpy as np


def safe_num(df, col):
    return pd.to_numeric(df[col], errors="coerce").fillna(0) if col in df.columns else pd.Series(0, index=df.index)


def base_sales(data):
    df = data.get("SALES", pd.DataFrame()).copy()
    if df.empty:
        return df
    for c in ["sales_qty", "sales_value", "mrp", "stock_qty", "target", "margin_pct", "promo_pct", "returns"]:
        if c not in df.columns:
            df[c] = 0
    if "margin_value" not in df.columns:
        df["margin_value"] = safe_num(df, "sales_value") * safe_num(df, "margin_pct") / 100
    if "net_sales_qty" not in df.columns:
        df["net_sales_qty"] = (safe_num(df, "sales_qty") - safe_num(df, "returns")).clip(lower=0)
    return df


def latest_month(df):
    if df.empty or "month" not in df.columns:
        return None
    vals = df["month"].dropna()
    return vals.max() if not vals.empty else None


def filter_df(df, params):
    if df.empty:
        return df
    out = df.copy()
    for key in ["chain_name", "chain_type", "region", "state", "city", "brand", "category", "sub_category", "pareto", "status", "outlet_name", "sku"]:
        val = params.get(key)
        if val and val != "All" and key in out.columns:
            out = out[out[key].astype(str).eq(str(val))]
    return out


def kpis(df, data):
    if df.empty:
        return {"sales": 0, "growth": 0, "qty": 0, "stock": 0, "stock_value": 0, "nod": 0,
                "oos": 0, "stores": 0, "skus": 0, "target": 0, "achievement": 0, "margin": 0}
    sales = float(df["sales_value"].sum())
    qty = float(df["sales_qty"].sum())
    stock = float(df["stock_qty"].sum())
    stock_value = float((df["stock_qty"] * df["mrp"]).sum())
    target = float(df["target"].sum())
    achievement = sales / target * 100 if target else 0
    avg_monthly_qty = qty / max(df["month"].nunique(), 1) if "month" in df.columns else qty
    nod = stock / avg_monthly_qty * 30 if avg_monthly_qty else 0
    oos = float((df["stock_qty"] <= 0).mean() * 100)
    stores = df["outlet_code"].nunique() if "outlet_code" in df.columns else df["outlet_name"].nunique()
    skus = df["sku_code"].nunique() if "sku_code" in df.columns else df["sku"].nunique()
    margin = float(df["margin_value"].sum())

    growth = 0
    if "month" in df.columns:
        lm = latest_month(df)
        if lm is not None:
            cur = df[df["month"] == lm]["sales_value"].sum()
            ly = df[df["month"] == lm - pd.DateOffset(years=1)]["sales_value"].sum()
            if ly:
                growth = (cur / ly - 1) * 100

    return {"sales": sales, "growth": growth, "qty": qty, "stock": stock,
            "stock_value": stock_value, "nod": nod, "oos": oos, "stores": stores,
            "skus": skus, "target": target, "achievement": achievement, "margin": margin}


def group_table(df, group, n=10):
    if df.empty or group not in df.columns:
        return []
    g = df.groupby(group, dropna=False).agg(
        sales_value=("sales_value", "sum"),
        sales_qty=("sales_qty", "sum"),
        stock_qty=("stock_qty", "sum"),
        margin_value=("margin_value", "sum"),
    ).reset_index()
    g["nod"] = np.where(g["sales_qty"] > 0, g["stock_qty"] / g["sales_qty"] * 30, 0)
    g["margin_pct"] = np.where(g["sales_value"] > 0, g["margin_value"] / g["sales_value"] * 100, 0)
    return g.sort_values("sales_value", ascending=False).head(n).round(2).to_dict("records")


def trend(df):
    if df.empty or "month" not in df.columns:
        return []
    g = df.groupby("month", as_index=False).agg(
        sales_value=("sales_value", "sum"),
        sales_qty=("sales_qty", "sum"),
        stock_qty=("stock_qty", "sum"),
        margin_value=("margin_value", "sum"),
    )
    g["month"] = g["month"].dt.strftime("%b-%Y")
    return g.to_dict("records")


def pareto(df):
    if df.empty:
        return []
    key = "sku" if "sku" in df.columns else "sku_code"
    g = df.groupby(key, dropna=False)["sales_value"].sum().sort_values(ascending=False).reset_index()
    total = g["sales_value"].sum()
    g["cum_pct"] = g["sales_value"].cumsum() / total * 100 if total else 0
    g["pareto"] = np.where(g["cum_pct"] <= 80, "Core", np.where(g["cum_pct"] <= 95, "Growth", "Tail"))
    return g.head(30).round(2).to_dict("records")


def opportunities(df, distribution=None):
    if df.empty:
        return []
    key = "sku" if "sku" in df.columns else "sku_code"
    dims = [key]
    if "outlet_name" in df.columns:
        dims.append("outlet_name")
    if "chain_name" in df.columns:
        dims.append("chain_name")
    g = df.groupby(dims, dropna=False).agg(
        sales_value=("sales_value", "sum"),
        sales_qty=("sales_qty", "sum"),
        stock_qty=("stock_qty", "sum"),
        mrp=("mrp", "mean"),
    ).reset_index()
    months = max(df["month"].nunique(), 1) if "month" in df.columns else 1
    g["velocity"] = g["sales_qty"] / months
    g["nod"] = np.where(g["velocity"] > 0, g["stock_qty"] / g["velocity"] * 30, 999)
    g["issue"] = "Monitor"
    g["priority"] = 0

    oos = g["stock_qty"] <= 0
    low = (g["nod"] < 15) & (g["velocity"] > 0)
    excess = g["nod"] > 90
    g.loc[oos, ["issue", "priority"]] = ["OOS / Sales at Risk", 100]
    g.loc[low & ~oos, ["issue", "priority"]] = ["Replenishment", 80]
    g.loc[excess, ["issue", "priority"]] = ["Excess Stock", 60]

    # High velocity + low distribution = expansion opportunity when distribution data exists.
    if distribution is not None and not distribution.empty:
        d = distribution.copy()
        if key in d.columns and "distribution" in d.columns:
            dg = d.groupby(key)["distribution"].mean().reset_index(name="distribution_pct")
            g = g.merge(dg, on=key, how="left")
            exp = (g["distribution_pct"] < 70) & (g["velocity"] > g["velocity"].median())
            g.loc[exp & (g["priority"] < 100), ["issue", "priority"]] = ["Distribution Opportunity", 90]
    else:
        g["distribution_pct"] = np.nan

    return g.sort_values(["priority", "sales_value"], ascending=[False, False]).head(50).round(2).to_dict("records")
