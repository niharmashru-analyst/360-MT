import io,re,time,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd,requests
from config import DATA_SOURCES,CACHE_MINUTES
cache={"t":0,"d":None}
options_cache={"t":0,"x":None}
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
 # calamine (Rust-based) parses xlsx roughly 5-7x faster than the default openpyxl engine,
 # which matters here since load() re-reads every source file on every cache miss/refresh.
 # Fall back to openpyxl for the rare file calamine can't parse (e.g. unusual formatting).
 try:return pd.read_excel(src,engine="calamine")
 except Exception:return pd.read_excel(src)
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
def load_options(force=False):
 # Filter values are deliberately independent from the heavy dashboard load.
 # IMPORTANT: never hold the global cache lock while doing network I/O. A slow
 # SharePoint request otherwise blocks every request handled by this gunicorn worker.
 global options_cache
 with _lock:
  if options_cache["x"] is not None and not force and time.time()-options_cache["t"] < CACHE_MINUTES*60:
   return options_cache["x"]

 # Read the sales source + two masters concurrently. Each request has a short
 # timeout specifically for the filter endpoint; a failed remote source is not
 # allowed to turn /api/options into a gateway timeout.
 jobs=[]
 for name in ("TERTIARY","PRIMARY","SKU_MASTER","OUTLET_MASTER"):
  src=DATA_SOURCES.get(name)
  if src:
   jobs.append((name,src))

 frames={}
 with ThreadPoolExecutor(max_workers=max(1,len(jobs))) as ex:
  futures={ex.submit(read_options_source,k,v):k for k,v in jobs}
  for fut,k in futures.items():
   try:
    frames[k]=fut.result(timeout=18)
   except Exception as e:
    last_errors[k]=f"Filter load skipped: {e}"
    frames[k]=None

 x=frames.get("TERTIARY")
 if x is None or x.empty:
  x=frames.get("PRIMARY")
 if x is None:
  x=pd.DataFrame()

 sm=frames.get("SKU_MASTER")
 if not x.empty and sm is not None and "sku_code" in x and "sku_code" in sm:
  sm=sm.drop_duplicates("sku_code")
  cols=[c for c in ["brand","category","sub_category","pareto","status","mrp"] if c in sm and c not in x]
  if cols:
   x=x.merge(sm[["sku_code"]+cols],on="sku_code",how="left")

 om=frames.get("OUTLET_MASTER")
 if not x.empty and om is not None and "outlet_code" in x and "outlet_code" in om:
  om=om.drop_duplicates("outlet_code")
  cols=[c for c in ["city","state","region","chain_name","chain_type","outlet_name"] if c in om and c not in x]
  if cols:
   x=x.merge(om[["outlet_code"]+cols],on="outlet_code",how="left")

 with _lock:
  options_cache={"t":time.time(),"x":x}
 return x

def read_options_source(name,src):
 """Short-timeout reader for /api/options. Local files are unchanged."""
 try:
  if src.startswith(("http://","https://")):
   url=normalize_url(src)
   r=requests.get(url,timeout=(3,15),headers=HEADERS)
   r.raise_for_status()
   ctype=r.headers.get("content-type","")
   if "html" in ctype.lower():
    raise ValueError("Remote source returned HTML instead of Excel")
   return std(read_excel_fast(io.BytesIO(r.content)))
  p=Path(src)
  if not p.exists():
   raise FileNotFoundError(f"No local file at {src}")
  return std(read_excel_fast(p))
 except Exception as e:
  print("OPTIONS DATA ERROR",name,src,e)
  return None

def load(force=False):
 global cache
 # IMPORTANT: only hold the lock while checking/updating the in-memory cache.
 # Never hold it during network/Excel I/O; otherwise a dashboard request can block
 # /api/options and make the browser receive a Render 502.
 with _lock:
  if cache["d"] is not None and not force and time.time()-cache["t"] < CACHE_MINUTES*60:
   return cache["d"]

 d={}
 with ThreadPoolExecutor(max_workers=max(1,len(DATA_SOURCES))) as ex:
  futures={ex.submit(read,k,v):k for k,v in DATA_SOURCES.items()}
  for fut,k in futures.items():
   try:d[k]=fut.result(timeout=55)
   except Exception as e:
    last_errors[k]=f"Timed out waiting for a response: {e}";d[k]=None
 x=d.get("TERTIARY")
 if x is None or x.empty:x=d.get("PRIMARY")
 if x is None:x=pd.DataFrame()
 if not x.empty and d.get("SKU_MASTER") is not None and "sku_code" in x and "sku_code" in d["SKU_MASTER"]:
  sm=d["SKU_MASTER"].drop_duplicates("sku_code");cols=[c for c in ["brand","category","sub_category","pareto","status","mrp"] if c in sm and c not in x]
  if cols:x=x.merge(sm[["sku_code"]+cols],on="sku_code",how="left")
 if not x.empty and d.get("OUTLET_MASTER") is not None and "outlet_code" in x and "outlet_code" in d["OUTLET_MASTER"]:
  om=d["OUTLET_MASTER"].drop_duplicates("outlet_code");cols=[c for c in ["city","state","region","store_status","store_format","store_area"] if c in om and c not in x]
  if cols:x=x.merge(om[["outlet_code"]+cols],on="outlet_code",how="left")
 d["SALES"]=x
 with _lock:cache={"t":time.time(),"d":d}
 return d
