"""Gera a versão estática do painel para publicar no GitHub Pages.

Lê os resultados de outputs/experimentos pela própria API (sem servidor)
e grava as respostas como arquivos JSON em frontend/public/data/. Depois
`VITE_STATIC=1 npm run build` produz um site que funciona sem Python.

Uso: python exportar_site.py
"""
from pathlib import Path
import json
import shutil
import sys

from fastapi.testclient import TestClient

import backend.main as api

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "frontend" / "public" / "data"
TREE_COLORS = ("E1", "E2", "E3", "E4")
VARIANTS = ("pearson", "spearman", "pearson_sem_mercado")


def save(client, route, name):
    response = client.get(route)
    if response.status_code != 200:
        print(f"  aviso: {route} respondeu {response.status_code}; arquivo {name} não gerado")
        return None
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(response.json(), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return response.json()


def main():
    if not (api.OUTPUT / "run.json").is_file():
        sys.exit("Sem resultados. Rode antes: python main.py --experimentos --sem-navegador")
    if DATA.exists():
        shutil.rmtree(DATA)
    client = TestClient(api.app)
    summary = save(client, "/api/summary", "summary.json")
    funds = save(client, "/api/funds", "funds.json") or []
    for fund in funds:
        save(client, f"/api/funds/{fund['ticker']}?top=8", f"fund/{fund['ticker']}.json")
    for relation in ("direct", "inverse"):
        save(client, f"/api/network?relation={relation}", f"network-{relation}.json")
    save(client, "/api/tree?color=louvain", "tree-louvain.json")
    for color in TREE_COLORS:
        for variant in VARIANTS:
            save(client, f"/api/tree?color={color}&variant={variant}", f"tree-{color}-{variant}.json")
    save(client, "/api/pairs?limit=1000", "pairs.json")
    protocol = save(client, "/api/protocol", "protocol.json") or {}
    save(client, "/api/portfolios", "portfolios.json")
    save(client, "/api/indicators", "indicators.json")
    for image in protocol.get("images", []):
        target = DATA / "images" / image
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(api.OUTPUT / image, target)
    stamp = (summary or {}).get("window", {}).get("last")
    (DATA / "meta.json").write_text(json.dumps({"static": True, "data_until": stamp}), encoding="utf-8")
    files = sum(1 for p in DATA.rglob("*") if p.is_file())
    print(f"{files} arquivos em {DATA.relative_to(ROOT)}. Agora: cd frontend && VITE_STATIC=1 npm run build")


if __name__ == "__main__":
    main()
