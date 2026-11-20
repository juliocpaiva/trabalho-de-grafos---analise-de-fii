"""Compara os pesos de Pearson e o peso composto discutido na consultoria."""

import networkx as nx
import pandas as pd
from sklearn.metrics import adjusted_rand_score

from algo_louvain import communities
from algo_mst import kruskal
from grafo_base import compound_similarity, similarity, topology
from visualizacao import network, pair_periods


def compare_models(corr, overlap, profile, temporal_pairs, output, settings, figures):
    """Aplica o mesmo limiar e os mesmos algoritmos nos dois modelos."""
    scores, pairs = compound_similarity(corr, profile)
    funds = list(scores.columns)
    coverage = {
        "eligible_funds": len(corr),
        "compared_funds": len(funds),
        "excluded_tickers": sorted(set(corr.columns) - set(funds)),
    }
    if len(funds) < 2 or pairs.empty:
        return {"status": "dados conjuntos insuficientes", **coverage}

    output.mkdir(parents=True, exist_ok=True)
    base = corr.loc[funds, funds]
    segments = profile.loc[funds, "segment"]
    rows, trees, graphs, partitions = [], {}, {}, {}
    # Cada execução aplica Louvain ao grafo limiarizado. A árvore usa
    # todos os pares calculáveis, mesmo aqueles abaixo do limiar.
    for name, matrix in (("pearson", base), ("composto", scores)):
        g = similarity(matrix, settings.tau)
        groups, modularity = communities(g, settings.resolution, settings.seed)
        tree, edges, info = kruskal(matrix)
        cross_edges = sum(segments[a] != segments[b] for a, b in g.edges)
        rows.append({"modelo": name, **topology(g), "communities": groups.nunique(),
                     "modularity": modularity, "arestas_entre_segmentos": cross_edges,
                     "proporcao_entre_segmentos": cross_edges / g.number_of_edges() if g.number_of_edges() else None,
                     "arestas_kruskal": info["edges"], "distancia_total_kruskal": info["total_distance"]})
        # No cenário composto, o valor de entrada representa uma pontuação.
        # O nome da coluna evita interpretar a pontuação como uma correlação.
        trees[name] = edges.rename(columns={"rho": "peso"})
        graphs[name], partitions[name] = g, groups
        if figures:
            network(g, groups, output, f"rede_{name}", f"Rede de similaridade — {name}", settings.seed)
            if name == "composto":
                network(tree, groups, output, "kruskal_composto", "Kruskal — modelo composto", settings.seed)

    for row in pairs.itertuples(index=False):
        for name in graphs:
            if graphs[name].has_edge(row.a, row.b):
                graphs[name][row.a][row.b].update(
                    rho=float(row.rho),
                    mesmo_segmento=int(row.mesmo_segmento),
                    mesma_faixa=int(row.mesma_faixa),
                    peso_composto=float(row.peso_composto),
                )
    for name, g in graphs.items():
        nx.write_graphml(g, output / f"rede_{name}.graphml")
        pairs[f"aresta_{name}"] = [g.has_edge(a, b) for a, b in pairs[["a", "b"]].itertuples(index=False, name=None)]
        trees[name].to_csv(output / f"kruskal_{name}.csv", index=False)

    pairs["pregoes_em_comum"] = [overlap.at[a, b] for a, b in pairs[["a", "b"]].itertuples(index=False, name=None)]
    pairs.to_csv(output / "pares.csv", index=False)
    pd.DataFrame(rows).to_csv(output / "comparacao.csv", index=False)
    pd.concat(partitions, axis=1).to_csv(output / "comunidades.csv")

    # Escolhe o par de segmentos distintos com o maior Pearson positivo
    # no histórico completo. Serve para ilustrar, pois o par foi escolhido
    # depois de observar a série inteira.
    example = pairs[(pairs.mesmo_segmento == 0) & (pairs.rho > 0)].nlargest(1, "rho")
    case = None
    if not example.empty:
        if temporal_pairs is not None:
            example = example.merge(temporal_pairs, on=["a", "b"], how="left")
        example.to_csv(output / "caso_entre_segmentos.csv", index=False)
        case = example.iloc[0].to_dict()
        if figures and pd.notna(case.get("rho_formation")) and pd.notna(case.get("rho_test")):
            pair_periods(case, output)

    before, after = (set(map(frozenset, g.edges)) for g in graphs.values())
    return {
        "status": "avaliada",
        **coverage,
        "pares_comparados": len(pairs),
        "jaccard_arestas": len(before & after) / len(before | after) if before | after else None,
        "ari_comunidades": float(adjusted_rand_score(partitions["pearson"], partitions["composto"])),
        "modelos": rows,
        "caso_entre_segmentos": case,
    }
