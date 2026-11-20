"""Testes da API do painel: sem resultados, com resultados e análise em segundo plano."""
import time

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import backend.main as api  # noqa: E402
from experimentos import Settings, run  # noqa: E402
from tests.test_analysis import cache  # noqa: E402,F401  (fixture reutilizada)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "OUTPUT", tmp_path / "saida")
    monkeypatch.setattr(api, "ROOT", tmp_path)
    return TestClient(api.app)


def test_without_results_every_route_answers_without_500(client):
    assert client.get("/api/summary").json()["status"] == "sem_resultados"
    for route in ("/api/funds", "/api/funds/T1", "/api/network", "/api/tree", "/api/pairs",
                  "/api/protocol", "/api/portfolios", "/api/indicators"):
        response = client.get(route)
        assert response.status_code == 404, route
        assert "Executar análise" in response.json()["detail"]
    assert client.post("/api/analyze").status_code == 409


def test_with_results_routes_return_dashboard_data(client, cache):
    path, dates = cache
    run(path, api.OUTPUT, Settings(cutoff=str(dates[24].date()), tau=.7, min_days=10, min_overlap=8,
                                   min_test_days=10, portfolio_size=2, min_events=1, protocol_repeats=2),
        figures=True)
    summary = client.get("/api/summary").json()
    assert summary["eligible_assets"] == 4 and summary["winners"]["melhor_equilibrio"]
    network = client.get("/api/network").json()
    assert len(network["nodes"]) == 4 and all("x" in n for n in network["nodes"])
    assert client.get("/api/network?relation=inverse").status_code == 200
    tree = client.get("/api/tree?color=E3").json()
    assert len(tree["edges"]) == 3 and tree["color"] == "E3"
    assert len(client.get("/api/protocol").json()["rows"]) == 12
    fund = client.get("/api/funds/t1").json()
    assert fund["ticker"] == "T1" and fund["pairs"]
    assert client.get("/api/pairs?cross_segment=true").status_code == 200
    assert client.get("/api/images/protocolo_e1_e4/protocolo_metricas.png").status_code == 200
    assert client.get("/api/images/../run.json").status_code == 404


def test_analyze_runs_in_background_and_finishes(client, cache, monkeypatch):
    path, dates = cache
    monkeypatch.setattr(api, "cache_dir", lambda: path)
    real_run = api.run
    monkeypatch.setattr(api, "run", lambda cache_, out, settings, quarantine=None: real_run(
        cache_, out, Settings(cutoff=str(dates[24].date()), tau=settings.tau, min_days=10, min_overlap=8,
                              min_test_days=10, portfolio_size=2, min_events=1, protocol_repeats=2),
        figures=False))
    assert client.post("/api/analyze?tau=0.7&repeats=2").status_code == 202
    for _ in range(100):
        status = client.get("/api/analyze/status").json()
        if status["state"] != "executando":
            break
        time.sleep(.1)
    assert status["state"] == "concluida", status["message"]
    assert client.get("/api/summary").json()["status"] == "avaliada"
