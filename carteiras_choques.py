"""Experimentos fora da amostra e associação histórica em dias de choque."""
from __future__ import annotations

from collections import Counter
from itertools import combinations

import numpy as np
import pandas as pd

from algo_louvain import communities
from grafo_base import correlation, similarity


def split_time(returns, cutoff):
    """Separa pregões de formação (até o corte) e avaliação (após o corte)."""
    cutoff = pd.Timestamp(cutoff)
    left, right = returns.loc[returns.index <= cutoff], returns.loc[returns.index > cutoff]
    if left.empty or right.empty:
        raise ValueError("A data de corte deve deixar sessões em ambas as janelas.")
    return left, right


def _choose(labels, liquidity, corr, k, relational=False):
    """Escolhe um fundo por vez, dando preferência ao grupo menos ocupado."""
    candidates = sorted(labels.index)
    selected, counts = [], Counter()
    while len(selected) < k:
        def score(t):
            previous = corr.loc[t, selected] if selected else pd.Series(dtype=float)
            # Na escolha relacional, uma correlação ausente recebe a pior
            # penalidade (1). Os últimos desempates são liquidez e ticker.
            rho = float(previous.fillna(1).mean()) if selected else 0.0
            return (counts[labels[t]], rho if relational else 0.0, -float(liquidity[t]), t)
        chosen = min(candidates, key=score)
        selected.append(chosen)
        counts[labels[chosen]] += 1
        candidates.remove(chosen)
    return selected


def avg_corr(corr, names):
    """Calcula a média dos pares distintos com correlação estimável."""
    values = np.array([corr.loc[a, b] for a, b in combinations(names, 2)], dtype=float)
    valid = values[np.isfinite(values)]
    return float(valid.mean()) if valid.size else None


def metrics(r, individual):
    """Resume uma carteira a partir dos retornos diários na mesma janela."""
    if len(r) < 2:
        raise ValueError("Ao menos dois dias conjuntos são necessários para métricas.")
    # Parte de 1 unidade de capital e reinveste os ganhos a cada pregão.
    # Drawdown mede a queda em relação ao maior valor acumulado até a data.
    wealth = (1 + r).cumprod()
    drawdown = wealth / wealth.cummax().clip(lower=1) - 1
    return {"days": len(r), "mean_pair_correlation": avg_corr(individual.corr(), list(individual)),
            "annual_volatility": float(r.std(ddof=1) * np.sqrt(252)),
            "total_return": float(wealth.iloc[-1] - 1),
            "max_drawdown": float(drawdown.min())}


def portfolios(train, test, meta, quality, size, min_overlap, tau, resolution, seed, min_test_days=20):
    """Monta duas carteiras de tamanho igual e compara no período posterior."""
    names = sorted(t for t in meta.index if quality.loc[t, "eligible"] and
                   meta.loc[t, "segment"] != "Sem classificação")
    if len(names) < size or size < 2:
        raise ValueError(f"Apenas {len(names)} fundos com segmento e dados elegíveis na formação.")
    corr, _ = correlation(train[names], min_overlap)
    member, mod = communities(similarity(corr, tau), resolution, seed)
    liq = quality.median_volume
    # A diversifica por segmento da CVM. B diversifica por comunidade e
    # prefere retornos menos correlacionados com as escolhas anteriores.
    a = _choose(meta.loc[names, "segment"], liq, corr, size)
    b = _choose(member, liq, corr, size, relational=True)
    alloc = pd.DataFrame([(label, pos, t, meta.loc[t, "segment"], member[t], 1 / size,
                           liq[t]) for label, values in (("A", a), ("B", b))
                          for pos, t in enumerate(values, 1)],
                         columns=["portfolio", "selection_order", "ticker", "segment", "formation_community",
                                  "weight", "formation_median_volume"])
    # Mesmas datas e mesmos fundos selecionados, sem retirar ativos com base em dados futuros.
    joint = test[sorted(set(a + b))].dropna()
    ret = pd.DataFrame(index=test.index, columns=["A", "B"], dtype=float)
    scores = []
    for label, values in (("A", a), ("B", b)):
        # A média dos retornos individuais equivale a refazer os pesos
        # iguais a cada pregão observado em comum.
        ret.loc[joint.index, label] = joint[values].mean(axis=1)
        row = {"portfolio": label, "assets": len(values), "segments": meta.loc[values, "segment"].nunique(),
               "formation_communities": member.loc[values].nunique(), "formation_correlation": avg_corr(corr, values),
               "eligible_formation_assets": len(names), "candidate_test_days": len(test),
               "joint_test_days": len(joint), "formation_modularity": mod}
        if len(joint) >= min_test_days:
            row.update(metrics(ret.loc[joint.index, label], joint[values]))
            row["status"] = "avaliada"
        else:
            row["status"] = "dias conjuntos insuficientes; carteiras preservadas"
        scores.append(row)
    return alloc, pd.DataFrame(scores), ret, member


def shocks(returns, labels, member, portfolio_returns, segment=None, quantile=0.05, threshold=None,
           min_events=5):
    """Compara os retornos médios em dias de choque e nos demais pregões.

    Um choque é um retorno médio negativo do segmento escolhido que
    atinge o limiar fixo ou fica no quantil inferior configurado.
    """
    if not 0 < quantile < 0.5 or (threshold is not None and not -1 < threshold < 0) or min_events < 1:
        raise ValueError("Quantil, limiar de choque ou mínimo de eventos inválido.")
    groups = labels.reindex(returns.columns).dropna()
    counts = groups[groups != "Sem classificação"].value_counts()
    viable = sorted(counts[counts >= 2].index)
    if segment is None and viable:
        segment = min(viable, key=lambda label: (-counts[label], label))
    if segment not in viable:
        raise ValueError(f"Segmento precisa de pelo menos dois FIIs. Disponíveis: {', '.join(viable)}.")
    trigger_members = list(groups[groups == segment].index)
    source = returns[trigger_members]
    # Exige retornos de pelo menos dois fundos e da maioria do segmento
    # antes de usar a média diária como gatilho.
    trigger = source.mean(axis=1).where(source.count(axis=1) >= max(2, len(trigger_members) // 2 + 1)).dropna()
    if trigger.empty:
        raise ValueError("Nenhum dia com maioria do segmento observada.")
    limit = float(trigger.quantile(quantile)) if threshold is None else float(threshold)
    event = (trigger <= limit) & (trigger < 0)
    events = trigger[event].rename("segment_return").to_frame()
    rows = []
    def describe(kind, name, series):
        series = series.reindex(trigger.index)
        affected, baseline = series[event].dropna(), series[~event].dropna()
        enough = len(affected) >= min_events and len(baseline) >= min_events
        rows.append({"group_type": kind, "group": name, "event_days": len(affected),
                     "other_days": len(baseline), "event_mean": affected.mean() if enough else None,
                     "other_mean": baseline.mean() if enough else None,
                     "mean_difference": affected.mean() - baseline.mean() if enough else None,
                     "negative_fraction_events": affected.lt(0).mean() if enough else None,
                     "status": "descritivo" if enough else "amostra insuficiente"})
    for t in sorted(set(returns.columns) - set(trigger_members)):
        describe("fundo fora do segmento", t, returns[t])
    # A parte de cada comunidade usada nesta comparação exclui os
    # próprios fundos que definiram o dia de choque.
    for comm in sorted(member.unique()):
        tickers = list(member.index[(member == comm) & ~member.index.isin(trigger_members)])
        if tickers:
            rets = returns[tickers]
            describe("comunidade sem fundos gatilho", str(comm),
                     rets.mean(axis=1).where(rets.count(axis=1) >= len(tickers) // 2 + 1))
    for label, series in portfolio_returns.items():
        describe("carteira fora da amostra", label, series)
    return events, pd.DataFrame(rows), {"segment": segment, "threshold": limit,
                 "mode": "fixed" if threshold is not None else "historical_quantile",
                 "quantile": quantile if threshold is None else None,
                 "trigger_members": trigger_members, "events": len(events), "valid_segment_days": len(trigger)}
