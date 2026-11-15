from math import sqrt

import networkx as nx
import numpy as np
import pandas as pd
import pytest

import fonte_yfinance as data
import grafo_base as graph
from algo_louvain import communities
from algo_mst import kruskal


def test_price_gaps_zero_volume_and_duplicate_dates():
    days = pd.date_range("2025-01-06", periods=7)
    prices = [100, 105, 999, 120, 132, 150, 165]
    rows = pd.DataFrame({"date": days, "ticker": "FII1", "adjusted": prices, "close": prices,
                         "volume": [1, 1, 0, 1, 1, 1, 1]})
    rows = pd.concat([rows.iloc[:-1], rows.iloc[[-1]].assign(adjusted=0), rows.iloc[[-1]]])
    aligned, _, _ = data.price_panels(rows, ["FII1"], days.delete(5))
    assert pd.isna(aligned.loc[days[2], "FII1"])
    aligned, _, _ = data.price_panels(rows[rows.date.ne(days[5])], ["FII1"], days)
    ret = data.returns_from_prices(aligned)["FII1"]
    assert ret.loc[days[1]] == pytest.approx(.05)
    assert ret.loc[days[4]] == pytest.approx(.10)
    assert ret.loc[[days[i] for i in (0, 2, 3, 5, 6)]].isna().all()
    assert aligned.loc[days[6], "FII1"] == 165


def test_quarantine_invalidates_boundary_returns_without_changing_other_assets():
    days = pd.date_range("2025-01-06", periods=5)
    prices = pd.DataFrame({"FII1": [100, 1, 1.1, 110, 121], "FII2": [20, 21, 22, 23, 24]}, index=days)
    mask = pd.DataFrame([("FII1", "2025-01-07", "2025-01-08", "erro na escala", "teste")],
                        columns=["ticker", "start", "end", "reason", "source"])
    a, q, v, log = data.apply_quarantine(prices, prices, prices * 10, mask)
    returns = data.returns_from_prices(a)
    assert log.adjusted_rows_masked.tolist() == [2]
    assert returns.FII1.iloc[:4].isna().all()
    assert returns.FII1.iloc[4] == pytest.approx(.1)
    assert a.FII2.equals(prices.FII2)
    assert q.FII1.isna().sum() == v.FII1.isna().sum() == 2
    assert prices.FII1.notna().all()


def test_signed_pearson_and_minimum_overlap():
    values = pd.DataFrame({"A": [1, 2, 3, 4, 5], "B": [2, 4, 6, 8, np.nan],
                           "C": [-1, -2, -3, -4, np.nan], "D": [1, 2, np.nan, np.nan, 5]})
    corr, counts = graph.correlation(values, 4)
    assert corr.loc["A", "B"] == pytest.approx(1)
    assert corr.loc["A", "C"] == pytest.approx(-1)
    assert pd.isna(corr.loc["A", "D"]) and counts.loc["A", "D"] == 3
    g = graph.similarity(corr, .9)
    assert set(g.edges) == {("A", "B")}
    assert set(nx.isolates(g)) == {"C", "D"}
    assert not g.is_directed() and not list(nx.selfloop_edges(g))


def test_modularity_of_known_communities_and_empty_network():
    c = pd.DataFrame(.05, index=list("ABCDEFG"), columns=list("ABCDEFG"))
    for group in ("ABC", "DEF"):
        c.loc[list(group), list(group)] = .9
    c.loc["C", "D"] = c.loc["D", "C"] = .15
    g = graph.similarity(c, .1)
    membership, q = communities(g, seed=19)
    assert membership.A == membership.B == membership.C
    assert membership.D == membership.E == membership.F
    assert membership.nunique() == 3 and q > .45
    pd.testing.assert_series_equal(membership, communities(g, seed=19)[0])
    isolated, q = communities(graph.similarity(c, .99))
    assert isolated.nunique() == 7 and q is None


def test_centrality_uses_inverse_strength():
    labels = list("ABC")
    corr = pd.DataFrame([[1,.95,.30],[.95,1,.95],[.30,.95,1]], index=labels, columns=labels)
    result = graph.centralities(graph.similarity(corr, .25))
    assert result.loc["B", "degree"] == 2
    assert result.loc["B", "strength"] == pytest.approx(1.90)
    assert result.loc["B", "betweenness"] == pytest.approx(1)
    assert result.loc["A", "betweenness"] == 0


def test_kruskal_forest_uses_all_valid_edges_and_minimum_cost():
    labels = list("ABCDE")
    corr = pd.DataFrame(np.nan, index=labels, columns=labels)
    for a, b, value in [("A", "B", .9), ("A", "C", .8), ("B", "C", .75), ("C", "D", -.2)]:
        corr.loc[a, b] = corr.loc[b, a] = value
    f, edges, stat = kruskal(corr)
    assert list(zip(edges.a, edges.b)) == [("A", "B"), ("A", "C"), ("C", "D")]
    assert set(f.nodes) == set(labels) and nx.is_forest(f)
    assert stat["components"] == 2 and stat["edges"] == 5 - 2
    assert stat["total_distance"] == pytest.approx(sum(sqrt(2 * (1 - rho)) for rho in (.9, .8, -.2)))


def test_snapshot_uses_only_published_version_and_contemporaneous_price():
    rows = [
        ("2025-01-01", "2025-02-02", 1, "A", 10),
        ("2025-01-01", "2025-03-02", 2, "B", 5),
        ("2025-02-01", "2025-03-15", 1, "C", 1),
    ]
    f = pd.DataFrame(rows, columns=["reference", "published", "version", "segment", "book_per_share"])
    f = f.assign(ticker="FUND", net_assets=1e6, monthly_yield=.01)
    quote = pd.DataFrame({"FUND": [12, 55]}, index=pd.to_datetime(["2025-01-31", "2025-02-28"]))
    result = data.snapshot(f, ["FUND", "MISSING"], "2025-02-28", quote)
    assert result.loc["FUND", "segment"] == "A"
    assert result.loc["FUND", "p_to_book"] == pytest.approx(1.2)
    assert result.loc["MISSING", "segment"] == "Sem classificação"
    assert pd.isna(result.loc["MISSING", "p_to_book"])


def test_quality_explains_non_trading_and_constant_funds():
    r = pd.DataFrame({"ok": [.01, .02, -.01, .04], "sparse": [0, np.nan, .02, np.nan],
                      "constant": [.01] * 4})
    v = pd.DataFrame({"ok": [10] * 4, "sparse": [5, 0, 6, 0], "constant": [5] * 4})
    q = data.assess(r, v, 3, .75, .75)
    assert q.index[q.eligible].tolist() == ["ok"]
    assert "baixa frequência" in q.loc["sparse", "exclusion"]
    assert "sem variação" in q.loc["constant", "exclusion"]
