import io,re,time,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd,requests
from openpyxl import load_workbook
from config import DATA_SOURCES,CACHE_MINUTES
cache={"t":0,"d":None}
_lock=threading.Lock()  # guards cache across the 4 gunicorn threads in this worker
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
HEADERS={"User-Agent":"Mozilla/5.0 (MT360 data loader)"}
last_errors={}  # {source_key: last error message}, surfaced on the Data Health page
def normalize_url(u):
 # OneDrive/SharePoint "share" links (…/:x:/g/personal/…) open the Excel Online *viewer*
 # page by default, not the raw file. Appending download=1 forces a raw download instead —
 # but this only works if the link's sharing permission is "Anyone with the link", since the
 # server has no Microsoft login session to satisfy an org/people-restricted link.
 if ("sharepoint.com" in u or "1drv.ms" in u or "onedrive.live.com" in u) and "download=1" not in u:
  u += ("&" if "?" in u else "?") + "download=1"
 return u
def read_excel_fast(src):
 # Use openpyxl only. python-calamine can terminate a Render worker with
 # exit code 139 when multiple Excel reads happen concurrently.
 return pd.read_excel(src, engine="openpyxl")

def _download_source(src):
 if src.startswith(("http://","https://")):
  url=normalize_url(src)
  r=requests.get(url, timeout=(8,30), headers=HEADERS)
  r.raise_for_status()
  if "html" in r.headers.get("content-type","").lower():
   raise ValueError("Excel URL returned HTML/login page; check sharing permission")
  return io.BytesIO(r.content)
 p=Path(src)
 if not p.exists(): raise FileNotFoundError(f"No local file at {src}")
 return p

def read_filter_columns(src, wanted):
 # Lightweight filter reader: openpyxl read_only reads only the required
 # columns row-by-row and never constructs a full pandas DataFrame.
 wb=load_workbook(_download_source(src), read_only=True, data_only=True)
 ws=wb[wb.sheetnames[0]]
 rows=ws.iter_rows(values_only=True)
 try: headers=next(rows)
 except StopIteration: wb.close(); return {}
 normalized=[norm(h) for h in headers]
 idx={}
 for i,h in enumerate(normalized):
  key=REV.get(h,h)
  if key in wanted and key not in idx: idx[key]=i
 values={k:set() for k in wanted if k in idx}
 for row in rows:
  for k,i in idx.items():
   if i < len(row) and row[i] not in (None,""): values[k].add(str(row[i]).strip())
 wb.close()
 return values

def read(name,src):
 try:
  if src.startswith(("http://","https://")):
   url=normalize_url(src)
   # (connect_timeout, read_timeout): fail fast on a dead host, but still allow a slow-but-alive
   # SharePoint response some room, without letting one source stall the whole load() call.
   r=requests.get(url,timeout=(10,45),headers=HEADERS);r.raise_for_status()
   ctype=r.headers.get("content-type","")
   if "html" in ctype.lower():
    # Common OneDrive/SharePoint failure mode: link returns a login/viewer page, not the file
    raise ValueError("Got an HTML page instead of the Excel file — check the SharePoint link's sharing permission is 'Anyone with the link', not restricted to specific people/org")
   result=std(read_excel_fast(io.BytesIO(r.content)))
  else:
   p=Path(src)
   if not p.exists():raise FileNotFoundError(f"No local file at {src}")
   result=std(read_excel_fast(p))
  last_errors.pop(name,None);return result
 except Exception as e:
  last_errors[name]=str(e);print("DATA ERROR",name,src,e);return None
def _build_dataset(names):
    """Load only the datasets needed by the current request.
    Keeping this small is critical on Render's low-memory instances.
    """
    d={}
    for k in names:
        src=DATA_SOURCES.get(k)
        if not src:
            d[k]=None
            continue
        d[k]=read(k,src)
    x=d.get("TERTIARY")
    if x is None or x.empty:
        x=d.get("PRIMARY")
    if x is None:
        x=pd.DataFrame()
    sm=d.get("SKU_MASTER")
    if not x.empty and sm is not None and "sku_code" in x and "sku_code" in sm:
        sm=sm.drop_duplicates("sku_code")
        cols=[c for c in ["brand","category","sub_category","pareto","status","mrp"] if c in sm and c not in x]
        if cols:
            x=x.merge(sm[["sku_code"]+cols],on="sku_code",how="left",copy=False)
    om=d.get("OUTLET_MASTER")
    if not x.empty and om is not None and "outlet_code" in x and "outlet_code" in om:
        om=om.drop_duplicates("outlet_code")
        cols=[c for c in ["city","state","region","store_status","store_format","store_area"] if c in om and c not in x]
        if cols:
            x=x.merge(om[["outlet_code"]+cols],on="outlet_code",how="left",copy=False)
    d["SALES"]=x
    return d

def load(force=False):
    global cache
    with _lock:
        if cache["d"] is not None and not force and time.time()-cache["t"]<CACHE_MINUTES*60:
            return cache["d"]
    # Do NOT load every workbook for the dashboard. OP_STOCK, CL_STOCK and TARGET
    # are independent datasets and can consume substantial memory. The dashboard's
    # current analytics only require sales + distribution + masters.
    d=_build_dataset(["TERTIARY","PRIMARY","DISTRIBUTION","SKU_MASTER","OUTLET_MASTER"])
    with _lock:
        cache={"t":time.time(),"d":d}
    return d

def load_all(force=False):
    """Explicit full load for diagnostics only; never used by normal dashboard requests."""
    global cache
    with _lock:
        if cache["d"] is not None and not force and time.time()-cache["t"]<CACHE_MINUTES*60:
            return cache["d"]
    d=_build_dataset(list(DATA_SOURCES.keys()))
    with _lock:
        cache={"t":time.time(),"d":d}
    return d
