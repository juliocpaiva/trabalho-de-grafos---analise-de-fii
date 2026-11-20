"""Orquestração dos experimentos e arquivos reprodutíveis."""
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
import hashlib
import json
import math
import platform

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

import carteiras_choques as analysis
import dashboard
import fonte_yfinance as data
import grafo_base as graph
import visualizacao as plots
from algo_louvain import communities
from algo_mst import kruskal
from comparacao_modelos import compare_models
from indicadores import fund_indicators
from protocolo import ProtocolSettings, rank, run_protocol, tree_preservation


@dataclass(frozen=True)
class Settings:
    """Reúne os parâmetros salvos com cada execução para poder repeti-la."""
    cutoff: str
    tau: float = .35
    thresholds: tuple = (.20, .35, .50, .65)
    resolution: float = 1.0
    resolutions: tuple = (.75, 1.0, 1.25)
    seed: int = 42
    min_days: int = 90
    min_overlap: int = 75
    coverage: float = .80
    trading: float = .80
    min_turnover_brl: float = 0.0
    portfolio_size: int = 6
    min_test_days: int = 60
    shock_segment: str | None = None
    shock_quantile: float = .05
    shock_threshold: float | None = None
    min_events: int = 5
    protocol_repeats: int = 30
    ifix_path: str | None = "config/ifix.csv"

    def validate(self):
        if self.min_days < 3 or self.min_overlap < 3 or self.min_test_days < 2 or self.portfolio_size < 2:
            raise ValueError("Mínimos de dados ou quantidade de fundos inválidos.")
        if not math.isfinite(self.min_turnover_brl) or self.min_turnover_brl < 0:
            raise ValueError("O giro financeiro mínimo precisa ser não negativo e finito.")
        if not 0 < self.coverage <= 1 or not 0 < self.trading <= 1:
            raise ValueError("Frações de qualidade devem estar em (0,1].")
        if any(not 0 < t <= 1 for t in (*self.thresholds, self.tau)):
            raise ValueError("Limiares devem estar em (0,1].")
        if any(not math.isfinite(r) or r <= 0 for r in (*self.resolutions, self.resolution)):
            raise ValueError("Resoluções devem ser positivas e finitas.")
        if not 0 < self.shock_quantile < .5 or self.min_events < 1:
            raise ValueError("Quantil ou mínimo de choques inválido.")
        if self.shock_threshold is not None and not -1 < self.shock_threshold < 0:
            raise ValueError("Limiar de choque deve estar em (-1,0).")
        if self.protocol_repeats < 2:
            raise ValueError("O protocolo E1–E4 exige pelo menos duas repetições.")


def _partition(returns, settings):
    """Aplica a mesma regra de correlação e Louvain a uma janela de retornos."""
    corr, overlap = graph.correlation(returns, settings.min_overlap)
    g = graph.similarity(corr, settings.tau)
    member, mod = communities(g, settings.resolution, settings.seed)
    return corr, overlap, g, member, mod


def _temporal(train, test, q1, q2, settings):
    """Compara duas redes usando somente fundos elegíveis nos dois períodos.

    ARI compara as partições sem depender dos números dados aos grupos.
    Jaccard divide as arestas presentes em ambas pelo total de arestas
    distintas nas duas redes. Também comparamos os pesos par a par.
    """
    common = sorted(set(q1.index[q1.eligible]) & set(q2.index[q2.eligible]))
    if len(common) < 2:
        return {"status": "fundos conjuntos insuficientes", "common_assets": len(common)}, None, None
    c1, n1, g1, m1, mod1 = _partition(train[common], settings)
    c2, n2, g2, m2, mod2 = _partition(test[common], settings)
    # Representa cada aresta como um conjunto, pois A–B e B–A são a mesma.
    e1, e2 = (set(map(frozenset, g.edges)) for g in (g1, g2))
    result = graph.pairs(c1, n1).rename(columns={"rho": "rho_formation", "overlap": "overlap_formation"})
    result = result.merge(graph.pairs(c2, n2).rename(columns={"rho": "rho_test", "overlap": "overlap_test"}),
                          on=["a", "b"])
    paired = result[["rho_formation", "rho_test"]].dropna()
    status = {
        "status": "avaliada", "common_assets": len(common), "paired_correlations": len(paired),
        "adjusted_rand": float(adjusted_rand_score(m1, m2)), "edge_jaccard": len(e1 & e2) / len(e1 | e2) if e1 | e2 else None,
        "pair_rho_pearson": paired.rho_formation.corr(paired.rho_test) if len(paired) >= 3 else None,
        "formation": {**graph.topology(g1), "modularity": mod1, "communities": m1.nunique()},
        "test": {**graph.topology(g2), "modularity": mod2, "communities": m2.nunique()}}
    return status, pd.concat([m1.rename("formation"), m2.rename("test")], axis=1), result


def _json_value(x):
    """Converte tipos NumPy e números ausentes para tipos aceitos em JSON."""
    if isinstance(x, np.generic):
        x = x.item()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: _json_value(v) for k, v in x.items()}
    if isinstance(x, (tuple, list)):
        return [_json_value(v) for v in x]
    return x


def _write_json(path, data_):
    path.write_text(json.dumps(_json_value(data_), indent=2, ensure_ascii=False, allow_nan=False),
                    encoding="utf-8")


def _protocol_stage(returns, train, test, names, corr, spearman, profile, settings, output, figures):
    """Roda E1–E4 com Pearson (base) e Spearman (variação) e grava as saídas."""
    folder = Path(output) / "protocolo_e1_e4"
    folder.mkdir(parents=True, exist_ok=True)
    config = ProtocolSettings(resolution=settings.resolution, seed=settings.seed,
                              repeats=settings.protocol_repeats)
    tables, partitions, summary = [], {}, {}
    for label, matrix, method in (("pearson", corr, "pearson"), ("spearman", spearman, "spearman")):
        windows = None
        if len(train) >= settings.min_overlap and len(test) >= settings.min_overlap:
            windows = (graph.correlation(train[names], settings.min_overlap, method)[0],
                       graph.correlation(test[names], settings.min_overlap, method)[0])
        table, parts, structures = run_protocol(matrix, config, profile.segment, label, windows)
        tables.append(table)
        partitions[label] = parts
        parts.to_csv(folder / f"particoes_{label}.csv")
        summary[label] = {"preservacao_pela_arvore_ari": tree_preservation(parts)}
        if figures:
            plots.protocol_partitions(structures["E3"], parts, profile.segment, folder, settings.seed,
                                      f"particoes_{label}")
    result = pd.concat(tables, ignore_index=True)
    # As notas comparam as oito execuções juntas (4 experimentos × 2 correlações).
    result = rank(result.drop(columns=[c for c in result if c.startswith(("nota_", "melhor_"))]))
    result.to_csv(folder / "e1_e4.csv", index=False)
    best = {label: result.loc[result[label], ["experimento", "correlacao"]].astype(str).agg(" ".join, axis=1).tolist()
            for label in ("melhor_qualidade", "melhor_custo", "melhor_equilibrio")}
    summary.update({"status": "avaliado", "repeticoes": config.repeats, "epsilon": config.epsilon,
                    "vencedores": best, "tabela": str(folder / "e1_e4.csv")})
    if figures:
        plots.protocol_metrics(result, folder)
    return result, partitions, summary


def run(cache, output, settings, figures=True, quarantine=None):
    """Executa os experimentos offline e exporta as evidências da análise."""
    settings.validate()
    market, universe, fundamentals, calendar, collected = data.load_cache(cache)
    adjusted, quote, volume = data.price_panels(market, universe.ticker.tolist(), calendar)
    excluded_rows, quarantine_manifest = None, None
    if quarantine:
        file = Path(quarantine)
        contents = file.read_bytes()
        adjusted, quote, volume, excluded_rows = data.apply_quarantine(
            adjusted, quote, volume, pd.read_csv(file, dtype=str))
        quarantine_manifest = {"path": str(quarantine), "sha256": hashlib.sha256(contents).hexdigest(),
                               "price_rows_masked": int(excluded_rows.adjusted_rows_masked.sum())}
    # Checa a qualidade separadamente no período inteiro, na formação e
    # na avaliação. A carteira precisa usar a qualidade da janela inicial.
    returns = data.returns_from_prices(adjusted)
    train, test = analysis.split_time(returns, settings.cutoff)
    def quality(r):
        return data.assess(r, volume.loc[r.index], settings.min_days, settings.coverage, settings.trading,
                           quote.loc[r.index], settings.min_turnover_brl)
    q, qtrain, qtest = map(quality, (returns, train, test))
    names = sorted(q.index[q.eligible])
    if len(names) < 2:
        raise ValueError("Menos de dois fundos elegíveis; confira as séries, a janela e os limites.")
    corr, overlap = graph.correlation(returns[names], settings.min_overlap)
    g, inverse_g = graph.signed_similarity(corr, settings.tau, overlap)
    members, mod = communities(g, settings.resolution, settings.seed)
    inverse_members, inverse_mod = communities(inverse_g, settings.resolution, settings.seed)
    # A rede descritiva usa a fotografia final. A montagem da carteira
    # recebe apenas a fotografia da data de corte.
    full_meta = data.snapshot(fundamentals, universe.ticker.tolist(), returns.index.max(), quote)
    train_meta = data.snapshot(fundamentals, universe.ticker.tolist(), settings.cutoff, quote)
    profile = (full_meta.loc[names].join(q).join(members)
               .join(inverse_members.rename("inverse_community")).join(graph.centralities(g)))
    profile["direct_community"] = profile["community"]
    forest, tree_edges, tree = kruskal(corr)
    # Toda floresta acíclica com V vértices e c componentes tem V - c arestas.
    if not tree["acyclic"] or tree["edges"] != tree["vertices"] - tree["components"]:
        raise RuntimeError("Floresta de Kruskal inválida.")
    # Anexa os atributos dos dois fundos a cada par. Assim o CSV permite
    # comparar os setores da CVM com as comunidades calculadas.
    pair_table = graph.pairs(corr, overlap)
    for endpoint in ("a", "b"):
        for attr in ("segment", "community", "p_to_book", "monthly_yield", "net_assets"):
            pair_table[f"{endpoint}_{attr}"] = pair_table[endpoint].map(profile[attr])
    pair_table["same_segment"] = (pair_table.a_segment == pair_table.b_segment).where(
        pair_table.a_segment.ne("Sem classificação") & pair_table.b_segment.ne("Sem classificação"))
    pair_table["same_community"] = pair_table.a_community.eq(pair_table.b_community)
    pair_table["in_similarity_graph"] = pair_table.rho.ge(settings.tau)
    pair_table["in_inverse_graph"] = pair_table.rho.le(-settings.tau)
    pair_table["relationship"] = pair_table.rho.map(
        lambda value: ("direta" if value >= settings.tau else
                       "inversa" if value <= -settings.tau else "abaixo do limiar")
        if pd.notna(value) else "indisponível")
    pair_table["p_to_book_gap"] = (pair_table.a_p_to_book - pair_table.b_p_to_book).abs()
    pair_table["monthly_yield_gap"] = (pair_table.a_monthly_yield - pair_table.b_monthly_yield).abs()
    pair_table = pair_table.sort_values("rho", ascending=False, kind="stable")
    signed_pair_table = graph.signed_pairs(corr, overlap, settings.tau)
    direct_pair_table = signed_pair_table[signed_pair_table.relation.eq("direta")]
    inverse_pair_table = signed_pair_table[signed_pair_table.relation.eq("inversa")]
    known = profile[profile.segment.ne("Sem classificação")]
    cross = pd.crosstab(profile.segment, profile.community)
    comparison = {
        "classified_assets": len(known),
        "adjusted_rand": float(adjusted_rand_score(known.segment, known.community)) if len(known) >= 2 else None,
        "normalized_mutual_information": float(normalized_mutual_info_score(known.segment, known.community))
        if len(known) >= 2 else None,
        "mixed_communities": int((known.groupby("community").segment.nunique() > 1).sum())}
    grouped = profile.groupby("community").agg(assets=("segment", "size"), segments=("segment", "nunique"))
    internal = pair_table[pair_table.same_community].groupby("a_community").rho.agg(["count", "mean"])
    grouped = grouped.join(internal.rename(columns={"count": "valid_internal_pairs", "mean": "mean_internal_rho"}))
    grouped["valid_internal_pairs"] = grouped.valid_internal_pairs.fillna(0).astype(int)
    group_corr = (pair_table.assign(group_1=np.minimum(pair_table.a_community, pair_table.b_community),
                                    group_2=np.maximum(pair_table.a_community, pair_table.b_community))
                  .groupby(["group_1", "group_2"]).rho.agg(["count", "mean"]).reset_index())
    # O limiar muda quais arestas entram na rede. A resolução muda como
    # Louvain agrupa os fundos de uma rede já construída.
    sensitivity = []
    assignments = []
    for tau in sorted(set((*settings.thresholds, settings.tau))):
        other = graph.similarity(corr, tau)
        for res in sorted(set((*settings.resolutions, settings.resolution))):
            nodes, modularity = communities(other, res, settings.seed)
            sensitivity.append({"tau": tau, "resolution": res, **graph.topology(other),
                                "communities": nodes.nunique(), "modularity": modularity,
                                "ari_vs_reference": adjusted_rand_score(members, nodes)})
            assignments.extend((tau, res, t, v) for t, v in nodes.items())
    sensitivity = pd.DataFrame(sensitivity)
    temporal, temporal_members, temporal_pairs = _temporal(train, test, qtrain, qtest, settings)
    limitations = [
        "Pearson mede associação linear histórica; modularidade, caminhos e choques não identificam causalidade.",
        "Amostra intencional, classificação declarada à CVM e cobertura variável; há possibilidade de viés de sobrevivência.",
        "Correlação par a par pode usar datas diferentes e a distância pode não satisfazer a desigualdade triangular.",
        "Carteiras usam pesos iguais rebalanceados diariamente nos dias conjuntos; sem custos, impostos ou execução real.",
        "Reapresentações públicas da CVM podem limitar a reconstrução de versões históricas.",
        "A comunidade de um isolado indica ausência de arestas ao limiar, não independência estatística.",
    ]
    # Registra carteiras ou choques sem dados suficientes no resumo.
    # Os resultados dos demais experimentos ainda podem ser exportados.
    alloc = scores = events = effects = None
    daily = pd.DataFrame(index=test.index)
    portfolio_status = "avaliada"
    try:
        alloc, scores, daily, _ = analysis.portfolios(train, test, train_meta, qtrain, settings.portfolio_size,
            settings.min_overlap, settings.tau, settings.resolution, settings.seed, settings.min_test_days)
        if scores.status.ne("avaliada").any():
            portfolio_status = scores.status.iloc[0]
    except ValueError as exc:
        portfolio_status = str(exc)
    try:
        events, effects, stress = analysis.shocks(returns[names], profile.segment, members, daily,
            settings.shock_segment, settings.shock_quantile, settings.shock_threshold, settings.min_events)
        stress["status"] = "avaliado" if len(events) >= settings.min_events else "amostra insuficiente"
    except ValueError as exc:
        stress = {"status": str(exc)}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    tables = {"quality": q.join(full_meta[["segment"]]), "quality_formation": qtrain,
              "quality_test": qtest, "formation_metadata": train_meta, "fund_profiles": profile,
              "returns": returns[names], "correlations": corr, "overlap": overlap,
              "pairs": pair_table, "segment_communities": cross, "communities": grouped,
              "direct_communities": members.rename("community"),
              "inverse_communities": inverse_members.rename("community"),
              "signed_edges": signed_pair_table, "direct_edges": direct_pair_table,
              "inverse_edges": inverse_pair_table,
              "community_pair_correlations": group_corr, "centralities": graph.centralities(g),
              "similarity_edges": pair_table[pair_table.in_similarity_graph],
              "kruskal_edges": tree_edges, "sensitivity": sensitivity,
              "sensitivity_members": pd.DataFrame(assignments, columns=["tau", "resolution", "ticker", "community"]),
              "temporal_members": temporal_members, "temporal_pairs": temporal_pairs,
              "portfolios": alloc, "portfolio_metrics": scores, "portfolio_returns": daily,
              "shock_dates": events, "shock_exposures": effects, "price_quarantine": excluded_rows}
    # Preserva o índice quando contém o ticker, a data ou outro rótulo
    # que identifica a linha. Tabelas de pares já trazem isso nas colunas.
    indexed = {"quality", "quality_formation", "quality_test", "formation_metadata", "fund_profiles",
               "returns", "correlations", "overlap", "segment_communities", "communities",
               "direct_communities", "inverse_communities", "centralities", "temporal_members",
               "portfolio_returns", "shock_dates"}
    for name, table in tables.items():
        if table is not None:
            table.to_csv(output / f"{name}.csv", index=name in indexed)

    # Coloca os mesmos atributos dos fundos nos dois GraphML para
    # permitir a inspeção dos vértices em programas como Gephi.
    for t in g:
        clean = {k: v for k, v in profile.loc[t, ["segment", "community", "direct_community",
                                                "inverse_community", "strength", "betweenness",
                                                "volatility", "p_to_book"]].items() if pd.notna(v)}
        for target in (g, inverse_g, forest):
            target.nodes[t].update({k: _json_value(v) for k, v in clean.items()})
    nx.write_graphml(g, output / "similarity.graphml")
    nx.write_graphml(inverse_g, output / "inverse_similarity.graphml")
    nx.write_graphml(forest, output / "kruskal.graphml")
    summary = {"settings": asdict(settings), "source": collected,
               "versions": {p: version(p) for p in ["numpy", "pandas", "networkx", "matplotlib", "scikit-learn", "yfinance", "requests"]},
               "python": platform.python_version(), "candidate_assets": len(universe), "price_quarantine": quarantine_manifest,
               "eligible_assets": len(names), "excluded_assets": len(universe) - len(names),
               "cvm_profile_coverage": {k: int(profile[k].notna().sum()) for k in
                                        ("p_to_book", "net_assets", "monthly_yield")},
               "window": {"first": str(returns.index.min().date()), "last": str(returns.index.max().date()),
                          "formation_last": str(train.index.max().date()), "test_first": str(test.index.min().date()),
                          "formation_days": len(train), "test_days": len(test)},
               "graph": {**graph.topology(g), "communities": members.nunique(), "modularity": mod},
               "signed_communities": {
                   "direct": {**graph.topology(g), "communities": members.nunique(), "modularity": mod},
                   "inverse": {**graph.topology(inverse_g), "communities": inverse_members.nunique(),
                               "modularity": inverse_mod},
               },
               "kruskal": tree, "comparison": comparison, "temporal": temporal,
               "portfolios": portfolio_status, "shock": stress, "limitations": limitations}
    # Compara as duas definições de peso no mesmo recorte de fundos com
    # atributos disponíveis. As carteiras acima preservam o modelo de referência.
    summary["comparacao_modelos"] = compare_models(corr, overlap, profile, temporal_pairs,
        output / "comparacao_modelos", settings, figures)
    summary["comparacao_modelos"]["pesos"] = dict(zip(
        ("pearson_positivo", "mesmo_segmento", "mesma_faixa"), graph.COMPOUND_WEIGHTS))
    summary["comparacao_modelos"]["limites_faixas_brl"] = graph.PROPERTY_BANDS_BRL
    segments = profile.segment.fillna("").to_dict()
    # Etapas 3, 4 e 8 do checklist: indicadores por FII, Spearman e E1–E4.
    spearman, _ = graph.correlation(returns[names], settings.min_overlap, method="spearman")
    correlation_gap = graph.compare_correlations(corr, spearman, overlap)
    indicators, benchmark = fund_indicators(returns[names], quote[names], volume[names], profile,
                                            settings.ifix_path)
    spearman.to_csv(output / "correlations_spearman.csv")
    correlation_gap.to_csv(output / "pearson_vs_spearman.csv", index=False)
    indicators.to_csv(output / "indicadores_fundos.csv")
    protocol, protocol_parts, summary["protocolo_e1_e4"] = _protocol_stage(
        returns, train, test, names, corr, spearman, profile, settings, output, figures)
    valid_gap = correlation_gap.dropna(subset=["diferenca"])
    summary["spearman"] = {
        "pares": int(len(valid_gap)),
        "diferenca_media_abs": float(valid_gap.diferenca_abs.mean()) if len(valid_gap) else None,
        "correlacao_entre_matrizes": float(valid_gap.pearson.corr(valid_gap.spearman)) if len(valid_gap) >= 3 else None,
    }
    summary["indicadores"] = {"beta_referencia": benchmark, "fundos": int(len(indicators))}
    dashboard_path = dashboard.write_dashboard(output, {
        "settings": {"tau": settings.tau, "resolution": settings.resolution,
                     "seed": settings.seed, "min_overlap": settings.min_overlap},
        "relations": {
            "direct": dashboard.relation_payload(g, members, mod, segments),
            "inverse": dashboard.relation_payload(inverse_g, inverse_members, inverse_mod, segments),
        },
        "protocol": dashboard.protocol_payload(protocol, protocol_parts["pearson"]),
    })
    summary["dashboard"] = str(dashboard_path)
    _write_json(output / "run.json", summary)
    if figures:
        plots.heatmap(spearman, output, "matriz_spearman", "Correlação de Spearman dos retornos diários", corr=True)
        plots.pearson_vs_spearman(correlation_gap, output)
        plots.heatmap(corr, output, "matriz_correlacao", "Correlação de Pearson dos retornos diários", corr=True)
        plots.heatmap(cross, output, "segmentos_comunidades", "Número de fundos por segmento e comunidade")
        plots.network(g, members, output, "rede_louvain", f"Rede de similaridade (ρ ≥ {settings.tau:g})", settings.seed)
        plots.network(inverse_g, inverse_members, output, "rede_louvain_inversa",
                      f"Rede de relações inversas (ρ ≤ {-settings.tau:g})", settings.seed)
        plots.network(forest, members, output, "estrutura_kruskal", "Estrutura mínima de Kruskal", settings.seed)
        plots.experiments(output, sensitivity, daily, effects if effects is not None else pd.DataFrame(), graph.centralities(g), temporal)
    return summary
