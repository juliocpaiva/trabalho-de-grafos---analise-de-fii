"""Testes do protocolo E1–E4, de Spearman e dos indicadores por FII."""
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import adjusted_rand_score

import grafo_base as graph
import indicadores
import protocolo


def _blocks(seed=7, days=300, size=4, noise=.004):
    """Dois blocos de FIIs movidos por fatores independentes."""
    rng = np.random.default_rng(seed)
    factors = rng.normal(0, .01, (days, 2))
    data = {f"{block}{i}": factors[:, b] + rng.normal(0, noise, days)
            for b, block in enumerate("AB") for i in range(size)}
    return pd.DataFrame(data, index=pd.bdate_range("2025-01-02", periods=days))


def test_edge_weights_are_positive_and_increase_with_rho():
    assert graph.edge_weight(1, "proporcional") == pytest.approx(1)
    assert graph.edge_weight(0, "proporcional") == pytest.approx(.5)
    assert graph.edge_weight(-1, "proporcional") == pytest.approx(0)
    assert graph.edge_weight(1, "distancia_inversa", .05) == pytest.approx(20)
    assert graph.edge_weight(-1, "distancia_inversa", .05) == pytest.approx(1 / 2.05)
    for model in graph.WEIGHT_MODELS:
        values = [graph.edge_weight(r, model) for r in np.linspace(-1, 1, 21)]
        assert all(b > a for a, b in zip(values, values[1:]))
    with pytest.raises(ValueError):
        graph.edge_weight(.5, "outro")


def test_complete_graph_keeps_every_estimable_pair_including_negative():
    names = list("ABC")
    corr = pd.DataFrame([[1, .6, -.4], [.6, 1, np.nan], [-.4, np.nan, 1]], index=names, columns=names)
    g = graph.complete_graph(corr, "proporcional")
    assert set(g.nodes) == set(names) and g.number_of_edges() == 2
    assert g["A"]["C"]["weight"] == pytest.approx(.3) and g["A"]["C"]["rho"] == pytest.approx(-.4)
    dist = graph.distance_matrix(corr, missing=2 ** .5)
    assert np.allclose(np.diag(dist), 0) and dist.at["B", "C"] == pytest.approx(2 ** .5)


def test_spearman_ignores_monotonic_nonlinearity():
    x = np.linspace(-3, 3, 120)
    returns = pd.DataFrame({"X": x, "Y": np.exp(2 * x)})
    pearson, overlap = graph.correlation(returns, 10)
    spearman, _ = graph.correlation(returns, 10, method="spearman")
    assert spearman.at["X", "Y"] == pytest.approx(1)
    assert pearson.at["X", "Y"] < .9
    table = graph.compare_correlations(pearson, spearman, overlap)
    assert table.loc[0, "diferenca"] == pytest.approx(1 - pearson.at["X", "Y"])
    with pytest.raises(ValueError):
        graph.correlation(returns, 10, method="kendall")


def test_both_trees_share_topology_and_have_n_minus_one_edges():
    corr, _ = graph.correlation(_blocks(), 50)
    trees = [protocolo.tree_graph(corr, model)[0] for model in graph.WEIGHT_MODELS]
    assert all(t.number_of_edges() == len(corr) - 1 for t in trees)
    assert {frozenset(e) for e in trees[0].edges} == {frozenset(e) for e in trees[1].edges}
    a, b = next(iter(trees[0].edges))
    assert trees[0][a][b]["weight"] != trees[1][a][b]["weight"]


def test_protocol_recovers_known_blocks_and_reports_metrics():
    returns = _blocks()
    corr, _ = graph.correlation(returns, 50)
    truth = pd.Series({t: t[0] for t in corr.columns})
    settings = protocolo.ProtocolSettings(repeats=3)
    table, parts, structures = protocolo.run_protocol(corr, settings, segments=truth,
                                                      windows=(corr, corr))
    assert table.experimento.tolist() == ["E1", "E2", "E3", "E4"]
    assert adjusted_rand_score(truth, parts.E2.reindex(truth.index)) == pytest.approx(1)
    e2 = table.set_index("experimento").loc["E2"]
    assert e2.silhouette > .5 and e2.separacao > .5 and e2.estabilidade_sementes == pytest.approx(1)
    assert e2.estabilidade_temporal_ari == pytest.approx(1)
    assert structures["E3"].number_of_edges() == len(corr) - 1
    assert (table.tempo_medio_ms > 0).all() and (table.memoria_pico_kb > 0).all()
    assert table[["melhor_qualidade", "melhor_custo", "melhor_equilibrio"]].any().all()
    assert set(protocolo.tree_preservation(parts)) == {
        "proporcional_E1_vs_E3", "distancia_inversa_E2_vs_E4",
        "modelos_direto_E1_vs_E2", "modelos_arvore_E3_vs_E4"}


def test_silhouette_is_undefined_for_one_group():
    corr, _ = graph.correlation(_blocks(), 50)
    dist = graph.distance_matrix(corr)
    assert protocolo.silhouette(dist, pd.Series(1, index=corr.columns)) is None


def test_fund_indicators_drawdown_beta_and_benchmark(tmp_path):
    dates = pd.bdate_range("2025-01-02", periods=60)
    rng = np.random.default_rng(3)
    market = pd.Series(rng.normal(0, .01, 60), index=dates)
    returns = pd.DataFrame({"X": 2 * market, "Y": market + rng.normal(0, .001, 60)})
    quote = pd.DataFrame(10.0, index=dates, columns=["X", "Y"])
    volume = pd.DataFrame(100.0, index=dates, columns=["X", "Y"])
    assert indicadores.max_drawdown(pd.Series([.10, -.50, .20])) == pytest.approx(-.5)
    table, source = indicadores.fund_indicators(returns, quote, volume)
    assert source.startswith("proxy") and table.volume_financeiro_medio_brl.eq(1000).all()
    level = 100 * (1 + market).cumprod()
    pd.DataFrame({"date": dates, "close": level}).to_csv(tmp_path / "ifix.csv", index=False)
    table, source = indicadores.fund_indicators(returns, quote, volume, ifix_path=tmp_path / "ifix.csv")
    assert source == "IFIX (B3)" and table.at["X", "beta"] == pytest.approx(2, abs=1e-6)
