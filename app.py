from flask import Flask, render_template, request, jsonify
from data_loader import load_all
from analytics import base_sales, filter_df, kpis, group_table, trend, pareto, opportunities

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/dashboard")
def dashboard():
    data = load_all()
    df = filter_df(base_sales(data), request.args)
    return jsonify({
        "kpis": kpis(df, data),
        "trend": trend(df),
        "chains": group_table(df, "chain_name", 10),
        "regions": group_table(df, "region", 10),
        "categories": group_table(df, "category", 10),
        "brands": group_table(df, "brand", 10),
        "stores": group_table(df, "outlet_name", 10),
        "skus": group_table(df, "sku", 10),
        "pareto": pareto(df),
        "opportunities": opportunities(df, data.get("DISTRIBUTION")),
    })


@app.route("/api/options")
def options():
    data = load_all()
    df = base_sales(data)
    cols = ["chain_name", "chain_type", "region", "state", "city", "brand", "category", "sub_category", "pareto", "status"]
    out = {}
    for c in cols:
        out[c] = sorted(df[c].dropna().astype(str).unique().tolist()) if c in df.columns else []
    return jsonify(out)


@app.route("/api/refresh")
def refresh():
    load_all(force=True)
    return jsonify({"ok": True})


@app.route("/api/health")
def health():
    data = load_all()
    return jsonify({
        "ok": True,
        "datasets": {k: (0 if v is None else len(v)) for k, v in data.items()},
        "sales_rows": len(data.get("SALES", [])),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
