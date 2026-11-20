"""Protocolo E1–E4: compara dois modelos de peso e dois caminhos de detecção.

| Exp. | Peso                         | Detecção                               |
|------|------------------------------|----------------------------------------|
| E1   | proporcional, max(ρ, 0)      | Louvain no grafo completo              |
| E2   | distância inversa, 1/(d+ε) − 1/(√2+ε) | Louvain no grafo completo     |
| E3   | proporcional                 | Kruskal → Louvain na árvore            |
| E4   | distância inversa            | Kruskal → Louvain na árvore            |

Toda partição é avaliada no grafo completo do próprio modelo, para que
E1 e E3 (e E2 e E4) sejam comparados na mesma régua. As duas árvores
têm a mesma topologia, pois os dois pesos crescem com ρ; muda só o peso
que Louvain recebe em cada aresta.
"""
from dataclasses import dataclass
from itertools import combinations
from time import perf_counter
import tracemalloc

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score

from algo_louvain import communities
from algo_mst import kruskal
from grafo_base import INVERSE_EPSILON, complete_graph, distance_matrix, edge_weight

EXPERIMENTS = {
    "E1": ("proporcional", "direto"),
    "E2": ("distancia_inversa", "direto"),
    "E3": ("proporcional", "kruskal"),
    "E4": ("distancia_inversa", "kruskal"),
}
# Pesos do índice de equilíbrio. Qualidade pesa mais que custo porque, com
# dezenas de FIIs, todos os métodos rodam em milissegundos.
BALANCE_WEIGHTS = {"qualidade": .7, "custo": .3}


@dataclass(frozen=True)
class ProtocolSettings:
    """Parâmetros salvos com cada execução do protocolo."""
    resolution: float = 1.0
    seed: int = 42
    repeats: int = 30
    epsilon: float = INVERSE_EPSILON


def tree_graph(corr, model, epsilon=INVERSE_EPSILON):
    """Kruskal sobre d = sqrt(2(1 − ρ)) e conversão das arestas para o peso do modelo."""
    forest, _, summary = kruskal(corr)
    tree = nx.Graph(model=model, epsilon=epsilon)
    tree.add_nodes_from(forest.nodes)
    for a, b, attrs in forest.edges(data=True):
        weight = edge_weight(attrs["rho"], model, epsilon)
        # Ligações da árvore com ρ ≤ 0 só existem para conectar; peso zero = fora do Louvain.
        if weight > 0:
            tree.add_edge(a, b, rho=attrs["rho"], distance=attrs["distance"], weight=weight)
    return tree, summary


def _detect(corr, model, path, settings, seed):
    """Executa um experimento e mede o tempo de cada etapa."""
    t0 = perf_counter()
    full = complete_graph(corr, model, settings.epsilon)
    t1 = perf_counter()
    structure, tree_seconds = full, 0.0
    if path == "kruskal":
        structure, _ = tree_graph(corr, model, settings.epsilon)
        tree_seconds = perf_counter() - t1
    t2 = perf_counter()
    members, structure_modularity = communities(structure, settings.resolution, seed)
    t3 = perf_counter()
    times = {"grafo_s": t1 - t0, "kruskal_s": tree_seconds, "louvain_s": t3 - t2, "total_s": t3 - t0}
    return full, structure, members, structure_modularity, times


def _peak_memory_kb(corr, model, path, settings):
    """Pico de memória alocada pelo Python durante uma execução completa."""
    tracemalloc.start()
    try:
        _detect(corr, model, path, settings, settings.seed)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak / 1024


def silhouette(dist, members):
    """Silhouette com a matriz de distâncias pronta (metric="precomputed").

    Vai de −1 a 1: perto de 1, cada FII está mais perto do próprio grupo
    que do grupo vizinho. Só é definida com 2 ≤ k ≤ n − 1 grupos.
    """
    labels = members.reindex(dist.index)
    k = labels.nunique()
    if not 2 <= k <= len(labels) - 1:
        return None
    return float(silhouette_score(dist.to_numpy(), labels.to_numpy(), metric="precomputed"))


def cohesion(corr, members):
    """Correlação média dentro dos grupos e entre grupos (coesão × separação)."""
    inside, outside = [], []
    for a, b in combinations(corr.columns, 2):
        rho = corr.at[a, b]
        if pd.notna(rho):
            (inside if members[a] == members[b] else outside).append(float(rho))
    within = float(np.mean(inside)) if inside else None
    between = float(np.mean(outside)) if outside else None
    gap = within - between if within is not None and between is not None else None
    return within, between, gap


def seed_stability(partitions):
    """ARI médio entre as partições de sementes diferentes (1 = sempre igual)."""
    scores = [adjusted_rand_score(partitions[i], partitions[j])
              for i, j in combinations(range(len(partitions)), 2)]
    return float(np.mean(scores)) if scores else None


def _normalize(series, higher_is_better=True):
    """Leva uma métrica para [0, 1]; valores iguais viram 1."""
    values = pd.to_numeric(series, errors="coerce")
    low, high = values.min(), values.max()
    if pd.isna(low) or high == low:
        return values.notna().astype(float)
    scaled = (values - low) / (high - low)
    return (scaled if higher_is_better else 1 - scaled).fillna(0)


def rank(table):
    """Acrescenta notas de qualidade, custo e equilíbrio e marca os vencedores.

    Uma partição degenerada (todos num grupo só, ou cada FII sozinho) não
    separa nada: a Silhouette fica indefinida e a estabilidade vale 1 por
    trivialidade. Ela recebe nota de qualidade zero e não pode vencer.
    """
    table = table.copy()
    table["particao_degenerada"] = table.comunidades.le(1) | table.comunidades.ge(table.fiis)
    valid = ~table.particao_degenerada
    quality = pd.concat([_normalize(table.modularidade_grafo_completo.where(valid)),
                         _normalize(table.silhouette.where(valid)),
                         _normalize(table.estabilidade_sementes.where(valid))],
                        axis=1).mean(axis=1).where(valid, 0.0)
    cost = pd.concat([_normalize(table.tempo_medio_ms, higher_is_better=False),
                      _normalize(table.memoria_pico_kb, higher_is_better=False)], axis=1).mean(axis=1)
    table["nota_qualidade"] = quality.round(4)
    table["nota_custo"] = cost.round(4)
    table["nota_equilibrio"] = (BALANCE_WEIGHTS["qualidade"] * quality
                                + BALANCE_WEIGHTS["custo"] * cost).round(4)
    for column, label in (("nota_qualidade", "melhor_qualidade"), ("nota_custo", "melhor_custo"),
                          ("nota_equilibrio", "melhor_equilibrio")):
        candidates = table[column].where(valid) if label != "melhor_custo" else table[column]
        table[label] = candidates.eq(candidates.max()) & candidates.notna()
    return table


def run_protocol(corr, settings=ProtocolSettings(), segments=None, label="pearson",
                 windows=None):
    """Executa E1–E4 sobre uma matriz de correlação.

    corr: matriz ticker × ticker (Pearson ou Spearman).
    segments: Series ticker → segmento, para ARI/NMI contra a classificação.
    windows: par (matriz da formação, matriz da avaliação) para medir se o
    experimento encontra os mesmos grupos em dois períodos (ARI temporal).
    Retorna (tabela de métricas, partições ticker × experimento, grafos usados).
    """
    if corr.shape[0] < 3:
        raise ValueError("O protocolo exige pelo menos três FIIs.")
    if settings.repeats < 2:
        raise ValueError("Use pelo menos duas repetições para medir tempo e estabilidade.")
    dist = distance_matrix(corr, missing=2 ** .5)
    known = None
    if segments is not None:
        seg = segments.reindex(corr.columns).fillna("Sem classificação")
        known = seg[seg.ne("Sem classificação")]
    rows, partitions, structures = [], {}, {}
    for name, (model, path) in EXPERIMENTS.items():
        # Uma execução de aquecimento evita que o primeiro tempo inclua cargas iniciais.
        _detect(corr, model, path, settings, settings.seed)
        runs = [_detect(corr, model, path, settings, settings.seed + i) for i in range(settings.repeats)]
        full, structure, members, structure_q, _ = runs[0]
        totals = np.array([r[4]["total_s"] for r in runs]) * 1000
        groups = [list(tickers) for tickers in members.groupby(members).groups.values()]
        full_q = (nx.community.modularity(full, groups, weight="weight", resolution=settings.resolution)
                  if full.number_of_edges() else None)
        within, between, gap = cohesion(corr, members)
        row = {
            "experimento": name, "correlacao": label, "peso": model,
            "deteccao": "Louvain no grafo completo" if path == "direto" else "Kruskal → Louvain na árvore",
            "fiis": len(members), "arestas_usadas": structure.number_of_edges(),
            "comunidades": int(members.nunique()),
            "comunidades_unitarias": int(members.value_counts().eq(1).sum()),
            "modularidade_estrutura": structure_q, "modularidade_grafo_completo": full_q,
            "silhouette": silhouette(dist, members),
            "rho_medio_interno": within, "rho_medio_entre_grupos": between, "separacao": gap,
            "estabilidade_sementes": seed_stability([r[2].reindex(members.index) for r in runs]),
            "tempo_medio_ms": float(totals.mean()), "tempo_desvio_ms": float(totals.std(ddof=1)),
            "tempo_kruskal_ms": float(np.mean([r[4]["kruskal_s"] for r in runs]) * 1000),
            "tempo_louvain_ms": float(np.mean([r[4]["louvain_s"] for r in runs]) * 1000),
            "memoria_pico_kb": _peak_memory_kb(corr, model, path, settings),
            "repeticoes": settings.repeats,
        }
        if known is not None and len(known) >= 2:
            row["ari_vs_segmento"] = float(adjusted_rand_score(known, members.reindex(known.index)))
            row["nmi_vs_segmento"] = float(normalized_mutual_info_score(known, members.reindex(known.index)))
        if windows is not None:
            first, second = windows
            common = sorted(set(first.columns) & set(second.columns))
            _, _, before, _, _ = _detect(first.loc[common, common], model, path, settings, settings.seed)
            _, _, after, _, _ = _detect(second.loc[common, common], model, path, settings, settings.seed)
            row["estabilidade_temporal_ari"] = float(adjusted_rand_score(
                before.reindex(common), after.reindex(common)))
        rows.append(row)
        partitions[name] = members
        structures[name] = structure
    table = rank(pd.DataFrame(rows))
    return table, pd.DataFrame(partitions).rename_axis("ticker"), structures


def tree_preservation(partitions):
    """Quanto a árvore preserva as comunidades do grafo completo (ARI E1×E3 e E2×E4)."""
    return {
        "proporcional_E1_vs_E3": float(adjusted_rand_score(partitions.E1, partitions.E3)),
        "distancia_inversa_E2_vs_E4": float(adjusted_rand_score(partitions.E2, partitions.E4)),
        "modelos_direto_E1_vs_E2": float(adjusted_rand_score(partitions.E1, partitions.E2)),
        "modelos_arvore_E3_vs_E4": float(adjusted_rand_score(partitions.E3, partitions.E4)),
    }
