"""Aplica Kruskal para ligar os FIIs pela menor soma de distâncias."""

from itertools import combinations
from math import sqrt

import networkx as nx
import pandas as pd


class DisjointSets:
    """Mantém os componentes já ligados pelas arestas escolhidas.

    Cada fundo começa sozinho. parent aponta para outro item no mesmo
    conjunto ou para o próprio fundo quando ele representa o conjunto.
    """
    def __init__(self, nodes):
        self.parent = {v: v for v in nodes}
        self.size = dict.fromkeys(self.parent, 1)

    def find(self, v):
        """Encontra o representante do componente de v."""
        # Aproxima o nó da raiz para reduzir o trabalho nas próximas buscas.
        while v != self.parent[v]:
            self.parent[v] = self.parent[self.parent[v]]
            v = self.parent[v]
        return v

    def union(self, a, b):
        """Une os componentes de a e b e informa se eram distintos."""
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        # Pendura o componente menor no maior para limitar a altura da árvore.
        if self.size[a] < self.size[b]:
            a, b = b, a
        self.parent[b] = a
        self.size[a] += self.size[b]
        return True


def kruskal(corr):
    """Retorna a árvore ou floresta, as arestas escolhidas e um resumo.

    A entrada é a matriz de Pearson. Quanto maior a correlação, menor a
    distância dada por sqrt(2 * (1 - rho)). A ordenação das E arestas
    candidatas custa O(E log E), depois de examinar os pares de fundos.
    """
    f = nx.Graph()
    f.add_nodes_from(sorted(corr.columns))
    # Pares sem correlação estimável ficam fora. Cada candidato carrega
    # a distância usada na ordenação e o rho original para a tabela final.
    candidates = []
    for a, b in combinations(f.nodes, 2):
        rho = corr.loc[a, b]
        if pd.notna(rho):
            candidates.append((sqrt(2 * (1 - float(rho))), a, b, float(rho)))
    sets = DisjointSets(f.nodes)
    chosen = []
    # Percorre do menor para o maior custo, com desempate pelos tickers.
    # Se os extremos já têm o mesmo representante, a aresta fecharia um ciclo.
    for distance, a, b, rho in sorted(candidates):
        if sets.union(a, b):
            chosen.append((a, b, rho, distance))
            f.add_edge(a, b, rho=rho, distance=distance)
    # Com c componentes, a floresta tem V - c arestas. Quando c = 1,
    # há uma única árvore que contém todos os V fundos.
    count = nx.number_connected_components(f)
    summary = {"vertices": len(f), "edges": len(chosen), "components": count,
               "connected": count == 1, "acyclic": nx.is_forest(f) if len(f) else True,
               "total_distance": f.size(weight="distance"), "candidate_edges": len(candidates)}
    return f, pd.DataFrame(chosen, columns=["a", "b", "rho", "distance"]), summary
