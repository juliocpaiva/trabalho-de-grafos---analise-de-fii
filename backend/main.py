"""API FastAPI que serve os resultados da análise para o painel React.

Lê os arquivos gerados por `main.py --experimentos` em outputs/experimentos
e permite disparar uma nova análise em segundo plano.
"""
from datetime import datetime
from pathlib import Path
import json
import math
import threading

import networkx as nx
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import dashboard
from experimentos import Settings, run

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "experimentos"
QUARANTINE = ROOT / "config" / "quarentena_precos.csv"
IFIX = ROOT / "config" / "ifix.csv"
NO_RESULTS = "Nenhum resultado ainda. Clique em Executar análise ou rode python main.py --experimentos."

app = FastAPI(title="Rede de FIIs", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Estado da análise disparada pelo painel. Só uma roda por vez.
_job = {"state": "parada", "message": "", "started": None, "finished": None, "tau": None}
_job_lock = threading.Lock()


def cache_dir():
    """Mesma regra do main.py: prefere a última coleta; senão, o snapshot de referência."""
    api = ROOT / "data" / "coleta_api"
    return api if (api / "collection.json").is_file() else ROOT / "data" / "cache"


def json_safe(value):
    """Converte NumPy, NaN e infinitos para tipos aceitos em JSON."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if value is None or isinstance(value, (int, str, bool)):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def read_csv(name, index_col=None, required=True):
    """Lê um CSV de resultados; sem arquivo, responde 404 com instrução clara."""
    path = OUTPUT / name
    if not path.is_file():
        if required:
            raise HTTPException(status_code=404, detail=NO_RESULTS)
        return None
    return pd.read_csv(path, index_col=index_col, dtype={"cnpj": str})


def records(frame):
    return json_safe(frame.to_dict(orient="records"))


def run_summary():
    path = OUTPUT / "run.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_ticker(ticker, known=None):
    """Aceita HGLG11, hglg11 ou HGLG11.SA e devolve o nome usado nos resultados."""
    ticker = ticker.strip().upper()
    options = [ticker, ticker + ".SA", ticker.removesuffix(".SA")]
    if known is not None:
        return next((t for t in options if t in known), options[1] if not ticker.endswith(".SA") else ticker)
    return ticker if ticker.endswith(".SA") else ticker + ".SA"


# ---------------------------------------------------------------- estado

@app.get("/api/health")
def health():
    return {"status": "ok", "results_available": (OUTPUT / "run.json").is_file(),
            "cache": str(cache_dir().relative_to(ROOT)), "cache_available": (cache_dir() / "collection.json").is_file()}


@app.get("/api/summary")
def summary():
    data = run_summary()
    if data is None:
        return {"status": "sem_resultados", "message": NO_RESULTS}
    graph = data.get("graph", {})
    protocol = data.get("protocolo_e1_e4", {})
    return json_safe({
        "status": "avaliada",
        "eligible_assets": data.get("eligible_assets"),
        "candidate_assets": data.get("candidate_assets"),
        "communities": graph.get("communities"),
        "edges": graph.get("edges"),
        "modularity": graph.get("modularity"),
        "window": data.get("window", {}),
        "settings": data.get("settings", {}),
        "comparison": data.get("comparison", {}),
        "kruskal": data.get("kruskal", {}),
        "winners": protocol.get("vencedores", {}),
        "spearman": data.get("spearman", {}),
        "beta_reference": data.get("indicadores", {}).get("beta_referencia"),
        "limitations": data.get("limitations", []),
        "source": "sintético" if str(data.get("source", {}).get("source", "")).upper() == "SINTÉTICO" else "dados públicos",
    })


# ---------------------------------------------------------------- fundos

@app.get("/api/funds")
def funds():
    profile = read_csv("fund_profiles.csv")
    indicators = read_csv("indicadores_fundos.csv", required=False)
    columns = [c for c in ("ticker", "name", "segment", "community", "inverse_community", "degree",
                           "strength", "betweenness", "volatility", "p_to_book", "monthly_yield", "net_assets")
               if c in profile]
    frame = profile[columns]
    if indicators is not None:
        extra = [c for c in ("retorno_anualizado", "drawdown_maximo", "beta", "volume_financeiro_medio_brl")
                 if c in indicators]
        frame = frame.merge(indicators[["ticker", *extra]], on="ticker", how="left")
    return records(frame.sort_values("ticker"))


@app.get("/api/funds/{ticker}")
def fund(ticker: str, top: int = 8):
    profile = read_csv("fund_profiles.csv")
    ticker = normalize_ticker(ticker, set(profile.ticker))
    row = profile.loc[profile.ticker.eq(ticker)]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"{ticker} não está entre os FIIs elegíveis.")
    data = row.iloc[0].to_dict()
    indicators = read_csv("indicadores_fundos.csv", required=False)
    if indicators is not None and ticker in set(indicators.ticker):
        data["indicadores"] = indicators.loc[indicators.ticker.eq(ticker)].iloc[0].to_dict()
    pairs = read_csv("pairs.csv")
    mine = pairs.loc[pairs.a.eq(ticker) | pairs.b.eq(ticker)].dropna(subset=["rho"]).copy()
    mine["peer"] = mine.b.where(mine.a.eq(ticker), mine.a)
    mine["peer_segment"] = mine.b_segment.where(mine.a.eq(ticker), mine.a_segment)
    mine = mine.sort_values("rho", ascending=False).head(max(1, min(top, 40)))
    data["pairs"] = records(mine[["peer", "peer_segment", "rho", "overlap", "same_segment", "same_community"]])
    partitions = read_csv("protocolo_e1_e4/particoes_pearson.csv", index_col="ticker", required=False)
    if partitions is not None and ticker in partitions.index:
        data["protocolo"] = partitions.loc[ticker].to_dict()
    return json_safe(data)


@app.get("/api/indicators")
def indicators():
    return records(read_csv("indicadores_fundos.csv"))


# ---------------------------------------------------------------- redes

def _edges_from(name):
    frame = read_csv(name, required=False)
    return frame if frame is not None else pd.DataFrame(columns=["a", "b", "rho", "overlap"])


@app.get("/api/network")
def network(relation: str = "direct"):
    """Rede direta (ρ ≥ τ) ou inversa (ρ ≤ −τ), com posições calculadas aqui."""
    if relation not in ("direct", "inverse"):
        raise HTTPException(status_code=422, detail="relation deve ser direct ou inverse.")
    profile = read_csv("fund_profiles.csv").set_index("ticker")
    column = "community" if relation == "direct" else "inverse_community"
    membership = profile[column] if column in profile else profile["community"]
    edges = _edges_from("direct_edges.csv" if relation == "direct" else "inverse_edges.csv")
    if relation == "direct" and edges.empty:
        edges = _edges_from("similarity_edges.csv")
    tau = (run_summary() or {}).get("settings", {}).get("tau")
    g = nx.Graph(tau=tau or 0)
    g.add_nodes_from(profile.index)
    for row in edges.itertuples(index=False):
        rho = float(row.rho)
        g.add_edge(row.a, row.b, rho=rho, weight=abs(rho), overlap=int(getattr(row, "overlap", 0) or 0))
    payload = dashboard.relation_payload(g, membership.fillna(0).astype(int), None,
                                         profile.segment.fillna("").to_dict())
    data = run_summary() or {}
    signed = data.get("signed_communities", {}).get(relation, {})
    payload["modularity"] = signed.get("modularity", data.get("graph", {}).get("modularity") if relation == "direct" else None)
    return json_safe(payload)


VARIANTS = ("pearson", "spearman", "pearson_sem_mercado")


@app.get("/api/tree")
def tree(color: str = "louvain", variant: str = "pearson"):
    """Árvore de Kruskal com posições Kamada-Kawai e cores por partição.

    color = louvain (comunidades da rede com limiar) ou E1, E2, E3, E4;
    variant = correlação usada no protocolo (pearson, spearman, pearson_sem_mercado).
    """
    if variant not in VARIANTS:
        raise HTTPException(status_code=422, detail=f"variant deve ser uma de {', '.join(VARIANTS)}.")
    edges = read_csv("kruskal_edges.csv")
    profile = read_csv("fund_profiles.csv").set_index("ticker")
    g = nx.Graph()
    g.add_nodes_from(profile.index)
    g.add_edges_from((r.a, r.b, {"distance": float(r.distance), "rho": float(r.rho)})
                     for r in edges.itertuples(index=False))
    pos = nx.kamada_kawai_layout(g, weight=None) if g.number_of_edges() else nx.circular_layout(g)
    membership = profile.community
    if color != "louvain":
        partitions = read_csv(f"protocolo_e1_e4/particoes_{variant}.csv", index_col="ticker", required=False)
        if partitions is None or color not in partitions:
            raise HTTPException(status_code=404, detail=f"Partição {color} indisponível. Rode a análise completa.")
        membership = partitions[color].reindex(profile.index)
    xs, ys = zip(*pos.values())
    span_x, span_y = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
    nodes = [{"ticker": t, "segment": profile.segment.get(t, ""),
              "community": int(membership.get(t, 0)) if pd.notna(membership.get(t)) else 0,
              "x": 40 + (pos[t][0] - min(xs)) / span_x * 920, "y": 40 + (pos[t][1] - min(ys)) / span_y * 600}
             for t in g.nodes]
    return json_safe({"color": color, "variant": variant, "communities": int(pd.Series([n["community"] for n in nodes]).nunique()),
                      "nodes": nodes, "edges": records(edges)})


# ---------------------------------------------------------------- pares e experimentos

@app.get("/api/pairs")
def pairs(limit: int = 200, cross_segment: bool = False, ticker: str = "", order: str = "rho"):
    """Pares ordenados por Pearson, com Spearman ao lado e filtro entre segmentos."""
    frame = read_csv("pairs.csv").dropna(subset=["rho"])
    spearman = read_csv("pearson_vs_spearman.csv", required=False)
    if spearman is not None:
        frame = frame.merge(spearman[["a", "b", "spearman", "diferenca"]], on=["a", "b"], how="left")
    if cross_segment:
        frame = frame[frame.same_segment.eq(False) | frame.same_segment.astype(str).eq("False")]
    if ticker:
        t = normalize_ticker(ticker, set(frame.a) | set(frame.b))
        frame = frame[frame.a.eq(t) | frame.b.eq(t)]
    if order == "diferenca" and "diferenca" in frame:
        frame = frame.reindex(frame.diferenca.abs().sort_values(ascending=False).index)
    elif order == "negativo":
        frame = frame.sort_values("rho")
    else:
        frame = frame.sort_values("rho", ascending=False)
    keep = [c for c in ("a", "b", "a_segment", "b_segment", "rho", "spearman", "diferenca", "overlap",
                        "same_segment", "same_community") if c in frame]
    return records(frame[keep].head(max(1, min(limit, 1000))))


@app.get("/api/protocol")
def protocol():
    table = read_csv("protocolo_e1_e4/e1_e4.csv")
    data = (run_summary() or {}).get("protocolo_e1_e4", {})
    images = [name for name in ("protocolo_e1_e4/protocolo_metricas.png", "protocolo_e1_e4/particoes_pearson.png",
                                "protocolo_e1_e4/particoes_pearson_sem_mercado.png",
                                "protocolo_e1_e4/particoes_spearman.png") if (OUTPUT / name).is_file()]
    return json_safe({"rows": table.to_dict(orient="records"), "winners": data.get("vencedores", {}),
                      "repeats": data.get("repeticoes"), "epsilon": data.get("epsilon"),
                      "market_mode": data.get("modo_de_mercado"),
                      "preservation": {k: v.get("preservacao_pela_arvore_ari") for k, v in data.items()
                                       if isinstance(v, dict) and "preservacao_pela_arvore_ari" in v},
                      "images": images})


@app.get("/api/portfolios")
def portfolios():
    returns = read_csv("portfolio_returns.csv")
    metrics = read_csv("portfolio_metrics.csv", required=False)
    allocation = read_csv("portfolios.csv", required=False)
    date_col = returns.columns[0]
    returns = returns.rename(columns={date_col: "date"}).dropna(subset=["A", "B"])
    return {"returns": records(returns), "metrics": records(metrics) if metrics is not None else [],
            "allocation": records(allocation) if allocation is not None else []}


@app.get("/api/images/{name:path}")
def image(name: str):
    path = (OUTPUT / name).resolve()
    if path.suffix.lower() != ".png" or OUTPUT.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    return FileResponse(path)


# ---------------------------------------------------------------- execução

def _run_analysis(tau, repeats):
    try:
        run(cache_dir(), OUTPUT,
            Settings(cutoff="2025-11-14", tau=tau, shock_segment="Shoppings",
                     protocol_repeats=repeats, ifix_path=str(IFIX)),
            quarantine=str(QUARANTINE))
        message, state = "Análise concluída.", "concluida"
    except Exception as exc:  # a mensagem vai para o painel
        message, state = f"{type(exc).__name__}: {exc}", "erro"
    with _job_lock:
        _job.update(state=state, message=message, finished=datetime.now().isoformat(timespec="seconds"))


@app.post("/api/analyze", status_code=202)
def analyze(tau: float = 0.35, repeats: int = 5):
    """Dispara a análise completa em segundo plano; acompanhe em /api/analyze/status."""
    if not 0 < tau <= 1:
        raise HTTPException(status_code=422, detail="O limiar deve estar entre 0 e 1.")
    if not 2 <= repeats <= 100:
        raise HTTPException(status_code=422, detail="Repetições devem estar entre 2 e 100.")
    if not (cache_dir() / "collection.json").is_file():
        raise HTTPException(status_code=409, detail="Sem dados em data/cache nem data/coleta_api. Rode python coletar.py.")
    with _job_lock:
        if _job["state"] == "executando":
            raise HTTPException(status_code=409, detail="Já existe uma análise em execução.")
        _job.update(state="executando", message="Calculando correlações, redes e E1–E4…",
                    started=datetime.now().isoformat(timespec="seconds"), finished=None, tau=tau)
    threading.Thread(target=_run_analysis, args=(tau, repeats), daemon=True).start()
    return dict(_job)


@app.get("/api/analyze/status")
def analyze_status():
    with _job_lock:
        return dict(_job)


# ---------------------------------------------------------------- front compilado

dist = ROOT / "frontend" / "dist"
if dist.is_dir():
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Rota da API não encontrada.")
        file = (dist / path).resolve()
        if path and dist.resolve() in file.parents and file.is_file():
            return FileResponse(file)
        return FileResponse(dist / "index.html")
