"""Encontra comunidades no grafo de correlações positivas."""

import networkx as nx
import numpy as np
import pandas as pd


def communities(g, resolution=1.0, seed=42):
    """Devolve a comunidade de cada FII e a modularidade da partição.

    A modularidade compara o peso das ligações dentro dos grupos com o que
    seria esperado a partir da força dos vértices. A resolução controla a
    escala do agrupamento e a semente fixa as escolhas aleatórias.
    """
    if not np.isfinite(resolution) or resolution <= 0:
        raise ValueError("A resolução deve ser positiva e finita.")
    active = [v for v, degree in g.degree() if degree > 0]
    # Ordena os tickers e as arestas antes de trocar os nomes por inteiros.
    # Isso ajuda a repetir a partição em processos Python diferentes.
    active.sort()
    lookup = {v: i for i, v in enumerate(active)}
    numeric = nx.Graph()
    numeric.add_nodes_from(range(len(active)))
    normalized = sorted((min(lookup[a], lookup[b]), max(lookup[a], lookup[b]), attrs["weight"])
                        for a, b, attrs in g.edges(data=True))
    numeric.add_weighted_edges_from(normalized)
    # O NetworkX tenta mover vértices para grupos com ganho de modularidade
    # e contrai os grupos encontrados para repetir a busca.
    found = (nx.community.louvain_communities(numeric, weight="weight", resolution=resolution,
             seed=seed) if active else [])
    # Fundos isolados recebem grupos individuais. Ordenamos os grupos para
    # rotular de forma estável por tamanho e tickers.
    parts = sorted([sorted(active[i] for i in s) for s in found] + [[v] for v in nx.isolates(g)],
                   key=lambda s: (-len(s), s))
    membership = pd.Series({v: i for i, part in enumerate(parts, 1) for v in part},
                           dtype=int, name="community").rename_axis("ticker").sort_index()
    # Um grafo sem arestas tem peso total zero. Nesse caso Q fica indefinido.
    modularity = (nx.community.modularity(g, parts, weight="weight", resolution=resolution)
                  if g.number_of_edges() else None)
    return membership, modularity
