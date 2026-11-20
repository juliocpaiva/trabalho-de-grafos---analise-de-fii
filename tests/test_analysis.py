import hashlib
import json

import networkx as nx
import numpy as np
import pandas as pd
import pytest

import carteiras_choques as analysis
import fonte_yfinance as data
import main as application
from experimentos import Settings, run


def test_main_opens_dashboard_after_analysis(monkeypatch, tmp_path, capsys):
    launched = []

    def analyze(cache, output, tau):
        output.mkdir(parents=True, exist_ok=True)
        (output / "dashboard.html").write_text("<html></html>", encoding="utf-8")

    def open_browser(uri, new):
        launched.append((uri, new))
        return False

    monkeypatch.setattr(application, "analisar", analyze)
    monkeypatch.setattr(application.webbrowser, "open", open_browser)
    application.main(["--saida", str(tmp_path)])

    expected = (tmp_path / "dashboard.html").resolve()
    assert launched == [(expected.as_uri(), 2)]
    assert str(expected) in capsys.readouterr().err


def test_metrics_count_initial_drawdown():
    ret = pd.Series([-.10, .05, .10, -.20])
    individual = pd.DataFrame({"A": ret, "B": 2 * ret})
    m = analysis.metrics(ret, individual)
    assert m["total_return"] == pytest.approx(.9 * 1.05 * 1.1 * .8 - 1)
    assert m["max_drawdown"] == pytest.approx(-.20)
    assert m["mean_pair_correlation"] == 1
    assert analysis.metrics(ret.iloc[:2], individual.iloc[:2])["max_drawdown"] == pytest.approx(-.10)


def test_portfolio_formation_does_not_use_test_data():
    dates = pd.date_range("2025-01-02", periods=30)
    a = np.tile([.01, -.02, .02, .005, -.01], 6)
    b = np.tile([-.015, .02, .01, -.005, .001], 6)
    r = pd.DataFrame({"A": a, "B": a * .8, "C": b, "D": b * .9}, index=dates)
    train, test = analysis.split_time(r, dates[14])
    assert train.index.max() < test.index.min()
    meta = pd.DataFrame({"segment": ["office", "mall", "office", "mall"]}, index=r.columns)
    q = pd.DataFrame({"eligible": True, "median_volume": [90, 80, 70, 60]}, index=r.columns)
    def compare(x):
        return analysis.portfolios(train, x, meta, q, 2, 8, .75, 1, 42, 2)
    alloc, score, daily, _ = compare(test)
    assert alloc.groupby("portfolio").ticker.apply(list).to_dict() == {"A": ["A", "B"], "B": ["A", "C"]}
    perturbed = test.assign(B=np.nan)
    alloc_new, score_new, _, _ = compare(perturbed)
    pd.testing.assert_frame_equal(alloc, alloc_new)
    assert score.joint_test_days.eq(len(test)).all()
    assert score_new.joint_test_days.eq(0).all()
    assert daily["A"].loc[test.index[0]] == pytest.approx(test[["A", "B"]].iloc[0].mean())


def test_sector_shock_excludes_trigger_funds_from_external_communities():
    dates = pd.date_range("2025-01-03", periods=7)
    r = pd.DataFrame({"A": [-.04,.01,-.05,.02,.03,-.06,.01],
                      "B": [-.06,.01,-.03,.02,.03,np.nan,.01],
                      "C": [-.02,.01,.02,.03,.02,.02,.01]}, index=dates)
    labels = pd.Series({"A": "mall", "B": "mall", "C": "office"})
    m = pd.Series({"A": 1, "B": 2, "C": 1})
    dates_, exposures, summary = analysis.shocks(r, labels, m, r[["C"]], "mall",
                                                  threshold=-.03, min_events=2)
    assert dates_.index.tolist() == [dates[0], dates[2]]
    assert summary["events"] == 2 and summary["valid_segment_days"] == 6
    row = exposures[exposures.group_type.str.startswith("comunidade")].iloc[0]
    assert row.event_mean == pytest.approx(0)
    assert row.negative_fraction_events == .5


@pytest.fixture
def cache(tmp_path):
    dates = pd.bdate_range("2025-01-02", periods=50)
    tickers = ["T1", "T2", "T3", "T4"]
    rng = np.random.default_rng(13)
    factors = rng.normal(0, .01, (len(dates), 2))
    frames = []
    for i, ticker in enumerate(tickers):
        price = 100 * (1 + factors[:, i // 2] + rng.normal(0, .001, len(dates))).cumprod()
        frames.append(pd.DataFrame({"date": dates, "ticker": ticker, "adjusted": price, "close": price,
                                    "volume": 200 - i * 10}))
    meta = pd.DataFrame({
        "ticker": tickers, "published": "2024-12-10", "reference": "2024-11-01", "version": 1,
        "segment": ["Lojas", "Lojas", "Escritórios", "Escritórios"], "net_assets": 1e6,
        "book_per_share": 101, "monthly_yield": .01, "source": "sintético para teste"}).reindex(columns=data.FUND)
    datasets = {"market.csv": pd.concat(frames), "universe.csv": pd.DataFrame({"ticker": tickers, "cnpj": ""}),
                "fundamentals.csv": meta}
    digests = {}
    for name, frame in datasets.items():
        path = tmp_path / name
        frame.to_csv(path, index=False)
        digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "collection.json").write_text(json.dumps({"files_sha256": digests}), encoding="utf-8")
    return tmp_path, dates


def test_offline_run_exports_auditable_outputs(cache):
    path, dates = cache
    root = path / "out"
    settings = Settings(cutoff=str(dates[24].date()), tau=.7, min_days=10, min_overlap=8,
                        min_test_days=10, portfolio_size=2, min_events=1)
    summary = run(path, root, settings, figures=False)
    assert summary["dashboard"] == str(root / "dashboard.html")
    assert summary["graph"]["communities"] == 2
    assert summary["kruskal"]["edges"] == 3 and summary["temporal"]["common_assets"] == 4
    assert summary["portfolios"] == "avaliada"
    assert nx.is_tree(nx.read_graphml(root / "kruskal.graphml"))
    comparison = summary["comparacao_modelos"]
    assert comparison["compared_funds"] == 4 and comparison["pares_comparados"] == 6
    assert set(summary["signed_communities"]) == {"direct", "inverse"}
    comparison_path = root / "comparacao_modelos"
    assert set(pd.read_csv(comparison_path / "comparacao.csv").modelo) == {"pearson", "composto"}
    assert len(pd.read_csv(comparison_path / "kruskal_composto.csv")) == 3
    assert set(nx.read_graphml(comparison_path / "rede_composto.graphml")) == {"T1", "T2", "T3", "T4"}
    assert set(nx.read_graphml(root / "inverse_similarity.graphml")) == {"T1", "T2", "T3", "T4"}
    assert {"direct_community", "inverse_community"}.issubset(
        pd.read_csv(root / "fund_profiles.csv").columns)
    assert {"rho", "relation", "strength", "overlap"}.issubset(
        pd.read_csv(root / "signed_edges.csv").columns)
    dashboard = (root / "dashboard.html").read_text(encoding="utf-8")
    assert "Relacionamentos entre FIIs" in dashboard and 'id="inverse-tab"' in dashboard
    assert "cdn." not in dashboard
    assert pd.read_csv(root / "pairs.csv").rho.count() == 6
    assert len(pd.read_csv(root / "sensitivity.csv")) == 15
    assert pd.read_csv(root / "portfolio_metrics.csv").days.tolist() == [25, 25]
    assert json.loads((root / "run.json").read_text(encoding="utf-8"))["versions"]["networkx"]


def test_cache_integrity_checks_inputs(cache):
    path, _ = cache
    with (path / "market.csv").open("a", encoding="utf8") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="market.csv"):
        data.load_cache(path)
