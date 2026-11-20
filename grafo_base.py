"""Constrói redes de similaridade e mede a centralidade dos FIIs."""

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
    """Cria a rede limiarizada a partir de Pearson ou de uma pontuação composta."""
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
            # que ligações fortes custam menos nos caminhos. Multiplicar
            # por um milhão permite usar custos inteiros com boa precisão.
            g.add_edge(a, b, weight=float(rho), cost=round(1_000_000 / rho))
    return g


# As faixas são fixas em reais e podem ser revistas sem trocar o algoritmo.
# Usamos 60% para o comportamento dos retornos e 20% para cada atributo.
PROPERTY_BANDS_BRL = (100_000_000, 500_000_000, 1_000_000_000)
COMPOUND_WEIGHTS = (0.60, 0.20, 0.20)


def compound_similarity(corr, profile):
    """Retorna uma matriz de pesos e detalha a contribuição de cada par.

    A pontuação usa a parte positiva de Pearson, segmento igual (0 ou 1)
    e faixa de patrimônio igual (0 ou 1). Mantemos apenas fundos com
    segmento conhecido e patrimônio positivo. Pares sem Pearson válido
    continuam ausentes para que os modelos usem a mesma base.
    """
    metadata = profile.reindex(corr.columns)
    assets = pd.to_numeric(metadata.net_assets, errors="coerce")
    segments = metadata.segment.fillna("").str.strip()
    known = segments.ne("") & segments.ne("Sem classificação") & assets.gt(0) & assets.lt(float("inf"))
    funds = sorted(metadata.index[known])
    bands = pd.cut(assets.loc[funds], bins=[0, *PROPERTY_BANDS_BRL, float("inf")],
                   labels=False, right=False)
    scores = pd.DataFrame(float("nan"), index=funds, columns=funds)
    rows = []
    w_rho, w_segment, w_band = COMPOUND_WEIGHTS
    for a, b in combinations(funds, 2):
        rho = corr.at[a, b]
        if pd.isna(rho):
            continue
        same_segment = int(segments[a] == segments[b])
        same_band = int(bands[a] == bands[b])
        parts = (w_rho * max(0.0, rho), w_segment * same_segment, w_band * same_band)
        score = sum(parts)
        scores.at[a, b] = scores.at[b, a] = score
        rows.append((a, b, rho, segments[a], segments[b], assets[a], assets[b],
                     bands[a] + 1, bands[b] + 1, same_segment, same_band, *parts, score))

    return scores, pd.DataFrame(rows, columns=[
        "a", "b", "rho", "segmento_a", "segmento_b", "patrimonio_a", "patrimonio_b",
        "faixa_a", "faixa_b", "mesmo_segmento", "mesma_faixa",
        "parte_pearson", "parte_segmento", "parte_patrimonio", "peso_composto",
    ])


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
