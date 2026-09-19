import os,traceback
from flask import Flask,render_template,request,jsonify
from data_loader import load,last_errors
from analytics import sales,filt,kpi,group,trend,dist,opp
app=Flask(__name__)

@app.errorhandler(Exception)
def on_error(e):
 # Any unhandled exception (bad/missing Excel file, bad merge key, etc.) comes back
 # as JSON the frontend can show, instead of Flask's default HTML 500 page.
 traceback.print_exc()
 return jsonify({'error':str(e)}),500

@app.route('/')
def home():return render_template('index.html')
@app.route('/api/options')
def options():
 # NEVER call load() here. load() reads all 8 workbooks and can exceed the
 # memory limit on a small Render instance. Filters only need lightweight
 # unique values from the sales file and master files.
 from data_loader import DATA_SOURCES, read_filter_columns, load_all
 fields=['chain_name','chain_type','region','state','city','brand','category','sub_category','pareto','status']
 out={c:set() for c in fields}
 errors={}
 sales_src=DATA_SOURCES.get('TERTIARY') or DATA_SOURCES.get('PRIMARY')
 for src_name in ['TERTIARY','PRIMARY']:
  src=DATA_SOURCES.get(src_name)
  if not src: continue
  try:
   vals=read_filter_columns(src, fields)
   for c,v in vals.items(): out[c].update(v)
   if any(out[c] for c in fields): break
  except Exception as e:
   errors[src_name]=str(e)
 # Enrich missing product filters from SKU master and missing location filters
 # from outlet master, still using the lightweight row reader.
 for src_name, wanted in [('SKU_MASTER',['brand','category','sub_category','pareto','status']),('OUTLET_MASTER',['region','state','city','chain_type'])]:
  try:
   vals=read_filter_columns(DATA_SOURCES[src_name], wanted)
   for c,v in vals.items(): out[c].update(v)
  except Exception as e:
   errors[src_name]=str(e)
 result={c:sorted(v) for c,v in out.items()}
 response=jsonify(result)
 response.headers['Cache-Control']='public, max-age=300'
 return response
@app.route('/api/dashboard')
def dashboard():
 d=load();x=filt(sales(d),request.args)
 return jsonify({'kpis':kpi(x),'trend':trend(x),'distribution':dist(d),'chains':group(x,'chain_name',12),'regions':group(x,'region',12),'cities':group(x,'city',12),'categories':group(x,'category',12),'brands':group(x,'brand',12),'stores':group(x,'outlet_name',20),'skus':group(x,'sku',20),'opportunities':opp(x,d)})
@app.route('/api/page/<p>')
def page(p):
 d=load();x=filt(sales(d),request.args);sets={'sales':['chain_name','region','city','category','brand'],'retailer':['chain_name','outlet_name'],'product':['category','sub_category','brand','sku'],'inventory':['chain_name','outlet_name','category'],'distribution':['chain_name','region','category','sku'],'commercial':['chain_name','category','brand'],'flow':['chain_name','region','category']}
 return jsonify({'kpis':kpi(x),'trend':trend(x),'tables':{c:group(x,c,30) for c in sets.get(p,['chain_name','category','sku'])},'distribution':dist(d),'opportunities':opp(x,d)})
@app.route('/api/refresh')
def refresh():
    from data_loader import clear_cache
    clear_cache()
    return jsonify({'ok':True})
@app.route('/api/health')
def health():
 d=load_all();return jsonify({'datasets':{k:(0 if v is None else len(v)) for k,v in d.items()},'errors':last_errors})
if __name__=='__main__':
 # debug=True is only safe for local dev on your own machine (it exposes a remote-code-execution
 # console on error pages). Production always runs via gunicorn (see render.yaml) which ignores this
 # block entirely, but keeping debug=False here means a stray `python app.py` in prod is still safe.
 app.run(host='0.0.0.0',port=5000,debug=os.getenv('FLASK_DEBUG','0')=='1')
