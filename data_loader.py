import io,re,time
from pathlib import Path
import pandas as pd,requests
from config import DATA_SOURCES,CACHE_MINUTES
cache={"t":0,"d":None}
ALIASES={"month":["month","month year","period","date"],"outlet_code":["outlet code","store code","outlet id","store id"],"outlet_name":["outlet name","store name","outlet","store"],"chain_name":["chain name","chain","retailer","retailer name"],"chain_type":["chain type","channel type","format","store type"],"location":["location","place"],"city":["city"],"state":["state"],"region":["region","zone"],"sku":["sku","product","product name"],"sku_code":["sku code","sku id","product code","ean","ean code"],"brand":["brand","brand name"],"category":["category"],"sub_category":["sub category","subcategory","sub-category"],"pareto":["pareto","pareto group"],"status":["status","sku status"],"sales_qty":["sales qty","sales quantity","qty","tertiary sales qty"],"sales_value":["sales value","sales","net sales","sales amount"],"mrp":["mrp","price"],"stock_qty":["stock qty","stock quantity","stock"],"target":["target","targets","sales target","target value"],"margin_pct":["margins","margin","margin %","margin pct"],"promo_pct":["promos%","promo %","promo pct","promotion %"],"distribution":["distribution","listed","availability","distributed"],"store_status":["store status","outlet status"],"store_format":["store format","format"],"store_area":["store area","area","sq ft","sqft"]}
REV={re.sub(r"[^a-z0-9]+"," ",v.lower()).strip():k for k,vs in ALIASES.items() for v in vs}
def norm(c):return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",str(c).lower())).strip()
def std(df):
 df=df.copy();df.columns=[norm(c) for c in df.columns];df=df.rename(columns={c:REV[c] for c in df.columns if c in REV})
 for c in ["sales_qty","sales_value","mrp","stock_qty","target","margin_pct","promo_pct","distribution","returns","store_area"]:
  if c in df:df[c]=pd.to_numeric(df[c],errors="coerce").fillna(0)
 if "month" in df:
  dt=pd.to_datetime(df.month,errors="coerce")
  if dt.notna().any():df["month"]=dt.dt.to_period("M").dt.to_timestamp()
 return df
def read(src):
 try:
  if src.startswith(("http://","https://")):
   r=requests.get(src,timeout=60);r.raise_for_status();return std(pd.read_excel(io.BytesIO(r.content)))
  p=Path(src);return std(pd.read_excel(p)) if p.exists() else None
 except Exception as e:print("DATA ERROR",src,e);return None
def load(force=False):
 global cache
 if cache["d"] is not None and not force and time.time()-cache["t"]<CACHE_MINUTES*60:return cache["d"]
 d={k:read(v) for k,v in DATA_SOURCES.items()}
 x=d.get("TERTIARY")
 if x is None:x=d.get("PRIMARY")
 if x is None:x=pd.DataFrame()
 if not x.empty and d.get("SKU_MASTER") is not None and "sku_code" in x and "sku_code" in d["SKU_MASTER"]:
  sm=d["SKU_MASTER"].drop_duplicates("sku_code");cols=[c for c in ["brand","category","sub_category","pareto","status","mrp"] if c in sm and c not in x]
  if cols:x=x.merge(sm[["sku_code"]+cols],on="sku_code",how="left")
 if not x.empty and d.get("OUTLET_MASTER") is not None and "outlet_code" in x and "outlet_code" in d["OUTLET_MASTER"]:
  om=d["OUTLET_MASTER"].drop_duplicates("outlet_code");cols=[c for c in ["city","state","region","store_status","store_format","store_area"] if c in om and c not in x]
  if cols:x=x.merge(om[["outlet_code"]+cols],on="outlet_code",how="left")
 d["SALES"]=x;cache={"t":time.time(),"d":d};return d
