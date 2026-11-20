from pathlib import Path
import json
import math

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from experimentos import Settings, run


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "experimentos"
app = FastAPI(title="Rede de FIIs", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def csv_records(name, limit=None):
    path = OUTPUT / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {name}")
    frame = pd.read_csv(path)
    if limit:
        frame = frame.head(limit)
    frame = frame.replace([float("inf"), float("-inf")], None).where(pd.notna(frame), None)
    return frame.to_dict(orient="records")


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if value is None:
        return None
    if isinstance(value, (int, str, bool)):
        return value
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


@app.get("/api/health")
def health():
    return {"status": "ok", "results_available": OUTPUT.exists()}


@app.get("/api/summary")
def summary():
    run_path = OUTPUT / "run.json"
    if not run_path.exists():
        return {
            "eligible_assets": 0,
            "communities": 0,
            "edges": 0,
            "modularity": None,
            "settings": {},
            "status": "Execute a análise completa.",
        }
    data = json.loads(run_path.read_text(encoding="utf-8"))
    funds = csv_records("fund_profiles.csv")
    edges = csv_records("similarity_edges.csv")
    communities = csv_records("communities.csv")
    return {
        "eligible_assets": len(funds),
        "communities": len(communities),
        "edges": len(edges),
        "modularity": clean(data.get("graph", {}).get("modularity")),
        "settings": data.get("settings", {}),
        "status": "avaliada",
    }


@app.get("/api/funds")
def funds():
    frame = pd.read_csv(OUTPUT / "fund_profiles.csv")
    columns = ["ticker", "name", "segment", "community", "degree", "strength", "betweenness", "eligible"]
    available = [column for column in columns if column in frame.columns]
    frame = frame[available]
    return json_safe(frame.to_dict(orient="records"))


@app.get("/api/funds/{ticker}")
def fund(ticker: str):
    ticker = ticker.strip().upper()
    if not ticker.endswith(".SA"):
        ticker += ".SA"
    frame = pd.read_csv(OUTPUT / "fund_profiles.csv", dtype={"cnpj": str})
    row = frame.loc[frame.ticker.eq(ticker)]
    if row.empty:
        raise HTTPException(status_code=404, detail="FII não encontrado nos resultados")
    fund_data = row.iloc[0].to_dict()
    pairs = pd.read_csv(OUTPUT / "pairs.csv")
    related = pairs.loc[pairs.a.eq(ticker) | pairs.b.eq(ticker)].head(10)
    fund_data["pairs"] = related.to_dict(orient="records")
    return json_safe(fund_data)


@app.get("/api/network")
def network():
    funds = csv_records("fund_profiles.csv")
    edges = csv_records("similarity_edges.csv")
    nodes = [
        {
            "ticker": item["ticker"],
            "community": item.get("community"),
            "segment": item.get("segment"),
            "degree": item.get("degree", 0),
        }
        for item in funds
    ]
    return {"nodes": nodes, "edges": edges}


@app.get("/api/correlation")
def correlation(limit: int = 100):
    return csv_records("pairs.csv", min(max(limit, 1), 500))


@app.get("/api/tree")
def tree():
    edges = pd.read_csv(OUTPUT / "kruskal_edges.csv")
    funds = pd.read_csv(OUTPUT / "fund_profiles.csv")
    attributes = funds.set_index("ticker")[["community", "segment"]].to_dict("index")
    result = edges.to_dict(orient="records")
    for edge in result:
        for endpoint in ("a", "b"):
            info = attributes.get(edge[endpoint], {})
            edge[f"{endpoint}_community"] = info.get("community")
            edge[f"{endpoint}_segment"] = info.get("segment")
    return json_safe(result)


@app.get("/api/portfolios")
def portfolios():
    result = json_safe(csv_records("portfolio_returns.csv"))
    metrics = json_safe(csv_records("portfolio_metrics.csv"))
    return {"returns": result, "metrics": metrics}


@app.post("/api/analyze")
def analyze(tau: float = 0.35):
    if not 0 < tau <= 1:
        raise HTTPException(status_code=422, detail="O limiar deve estar entre 0 e 1.")
    try:
        result = run(
            ROOT / "data" / "coleta_api",
            OUTPUT,
            Settings(cutoff="2025-11-14", tau=tau, shock_segment="Shoppings"),
            quarantine=str(ROOT / "config" / "quarentena_precos.csv"),
        )
        return {
            "status": "concluída",
            "eligible_assets": result["eligible_assets"],
            "communities": result["graph"]["communities"],
            "edges": result["graph"]["edges"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/images/{name}")
def image(name: str):
    if "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Nome de imagem inválido")
    path = (OUTPUT / name).resolve()
    if not path.exists() or OUTPUT.resolve() not in path.parents:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(path)


dist = ROOT / "frontend" / "dist"
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        file = dist / path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(dist / "index.html")
