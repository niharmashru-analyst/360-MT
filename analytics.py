import pandas as pd,numpy as np
def sales(d):
 x=d.get("SALES",pd.DataFrame())
 if x.empty:return x
 for c in ["sales_qty","sales_value","mrp","stock_qty","target","margin_pct","promo_pct"]:
  if c not in x:x[c]=0
 if "margin_value" not in x:x["margin_value"]=x.sales_value*x.margin_pct/100
 return x
def filt(x,p):
 for c in ["chain_name","chain_type","region","state","city","brand","category","sub_category","pareto","status","outlet_name","sku"]:
  v=p.get(c)
  if v and v!="All" and c in x:x=x[x[c].astype(str)==str(v)]
 return x
def latest(x):
 z=x.month.dropna() if "month" in x else pd.Series(dtype="datetime64[ns]");return z.max() if len(z) else None
def kpi(x):
 if x.empty:return {a:0 for a in ["sales","growth","ach","qty","stock","stock_value","nod","oos","stores","skus","margin","margin_pct","target"]}
 lm=latest(x);cur=x[x.month==lm] if lm is not None else x;ly=x[x.month==lm-pd.DateOffset(years=1)] if lm is not None else x.iloc[0:0]
 sv=cur.sales_value.sum();l=ly.sales_value.sum();q=cur.sales_qty.sum();st=cur.stock_qty.sum();tar=cur.target.sum();mar=cur.margin_value.sum();vel=q/max(x.month.nunique(),1)
 return {"sales":float(sv),"growth":float((sv/l-1)*100 if l else 0),"ach":float(sv/tar*100 if tar else 0),"qty":float(q),"stock":float(st),"stock_value":float((cur.stock_qty*cur.mrp).sum()),"nod":float(st/vel*30 if vel else 0),"oos":float((cur.stock_qty<=0).mean()*100),"stores":int(cur.outlet_code.nunique()) if "outlet_code" in cur else 0,"skus":int(cur.sku_code.nunique()) if "sku_code" in cur else 0,"margin":float(mar),"margin_pct":float(mar/sv*100 if sv else 0),"target":float(tar)}
def group(x,c,n=30):
 if x.empty or c not in x:return []
 g=x.groupby(c,dropna=False).agg(sales=("sales_value","sum"),qty=("sales_qty","sum"),stock=("stock_qty","sum"),margin=("margin_value","sum"),target=("target","sum")).reset_index()
 lm=latest(x);g["growth"]=0
 if lm is not None:
  a=x[x.month==lm].groupby(c).sales_value.sum();b=x[x.month==lm-pd.DateOffset(years=1)].groupby(c).sales_value.sum();g["growth"]=g[c].map(((a-b)/b.replace(0,np.nan)*100).to_dict()).fillna(0)
 g["ach"]=np.where(g.target>0,g.sales/g.target*100,0);g["margin_pct"]=np.where(g.sales>0,g.margin/g.sales*100,0)
 return g.sort_values("sales",ascending=False).head(n).round(2).to_dict("records")
def trend(x):
 if x.empty:return []
 g=x.groupby("month").agg(sales=("sales_value","sum"),qty=("sales_qty","sum"),stock=("stock_qty","sum"),margin=("margin_value","sum")).reset_index();g["month"]=g.month.dt.strftime("%b-%Y");return g.round(2).to_dict("records")
def dist(d):
 z=d.get("DISTRIBUTION")
 if z is None or z.empty or "distribution" not in z:return {"pct":None,"gap":0}
 return {"pct":float(z.distribution.mean()*100),"gap":int((z.distribution==0).sum())}
def opp(x,d):
 if x.empty:return []
 keys=[c for c in ["chain_name","outlet_name","sku","sku_code","brand","category"] if c in x];g=x.groupby(keys).agg(sales=("sales_value","sum"),qty=("sales_qty","sum"),stock=("stock_qty","sum")).reset_index();m=max(x.month.nunique(),1);g["velocity"]=g.qty/m;g["nod"]=np.where(g.velocity>0,g.stock/g.velocity*30,999);g["issue"]="Monitor";g["score"]=10
 g.loc[g.stock<=0,["issue","score"]]=["OOS / Sales Risk",100];g.loc[(g.nod<15)&(g.stock>0),["issue","score"]]=["Replenishment",90];g.loc[g.nod>90,["issue","score"]]=["Excess Stock",70]
 z=d.get("DISTRIBUTION")
 if z is not None and not z.empty and "distribution" in z and "sku_code" in g and "sku_code" in z:
  dd=z.groupby("sku_code").distribution.mean()*100;g["distribution_pct"]=g.sku_code.map(dd);mask=(g.distribution_pct<70)&(g.velocity>g.velocity.median());g.loc[mask&(g.score<100),["issue","score"]]=["Distribution Opportunity",95]
 else:g["distribution_pct"]=np.nan
 return g.sort_values(["score","sales"],ascending=False).head(100).round(2).to_dict("records")
