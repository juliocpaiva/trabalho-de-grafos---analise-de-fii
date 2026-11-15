"""Constrói o grafo de correlações e mede a centralidade dos FIIs."""

from itertools import combinations

import networkx as nx
import pandas as pd


def correlation(returns, min_overlap):
    """Retorna as matrizes de correlação de Pearson e de pregões em comum.

    Cada par usa somente as datas em que os dois fundos têm retorno válido.
    Pares sem a amostra mínima ou sem variação mantêm a correlação ausente.
    """
    if min_overlap < 3:
        raise ValueError("A correlação exige ao menos três observações em comum.")
    cols = sorted(returns.columns)
    values = returns[cols]
    # A máscara vale 1 onde há retorno. O produto de duas colunas soma
    # quantas vezes os dois fundos têm valor na mesma linha.
    mask = values.notna().astype("int64")
    overlap = mask.T @ mask
    return values.corr(method="pearson", min_periods=min_overlap).clip(-1, 1), overlap


def pairs(corr, overlap):
    """Transforma cada par distinto em uma linha para consulta e exportação."""
    return pd.DataFrame(
        [(a, b, corr.loc[a, b], int(overlap.loc[a, b])) for a, b in combinations(corr.columns, 2)],
        columns=["a", "b", "rho", "overlap"])


def similarity(corr, tau):
    """Cria um grafo não direcionado com uma aresta por par que atinge tau."""
    if not 0 < tau <= 1:
        raise ValueError("O limiar deve estar em (0, 1].")
    g = nx.Graph(tau=tau)
    # Insere também os fundos que terminam sem arestas. Eles continuam
    # aparecendo na análise como vértices isolados.
    g.add_nodes_from(sorted(corr.columns))
    for a, b in combinations(g.nodes, 2):
        rho = corr.loc[a, b]
        if pd.notna(rho) and rho >= tau:
            # weight mede a força da ligação. cost aproxima 1/rho, de modo
            # que correlações fortes custam menos nos caminhos. Multiplicar
            # por um milhão permite usar custos inteiros com boa precisão.
            g.add_edge(a, b, weight=float(rho), cost=round(1_000_000 / rho))
    return g


def centralities(g):
    """Resume a posição do fundo pelo grau, pela força e pela intermediação.

    Grau conta vizinhos e força soma os pesos das arestas incidentes.
    Intermediação mede quanto o fundo aparece nos caminhos de menor custo
    entre outros pares de vértices.
    """
    between = nx.betweenness_centrality(g, weight="cost", normalized=True)
    result = pd.DataFrame({"degree": dict(g.degree()),
                           "strength": dict(g.degree(weight="weight")),
                           "betweenness": between}).rename_axis("ticker")
    return result.sort_values(["betweenness", "strength"], ascending=False, kind="stable")


def topology(g):
    """Resume conectividade e densidade, a fração de arestas possíveis presentes."""
    return {"vertices": len(g), "edges": g.number_of_edges(), "density": nx.density(g),
            "components": nx.number_connected_components(g),
            "isolates": nx.number_of_isolates(g),
            "largest_component": max(map(len, nx.connected_components(g)), default=0)}
