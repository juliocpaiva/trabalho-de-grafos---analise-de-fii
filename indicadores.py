"""Indicadores financeiros por FII (etapa 3 do checklist)."""
from pathlib import Path

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def max_drawdown(returns):
    """Maior queda do patrimônio em relação ao pico anterior, em fração (ex.: −0,12)."""
    r = returns.dropna()
    if r.empty:
        return np.nan
    wealth = (1 + r).cumprod()
    return float((wealth / wealth.cummax().clip(lower=1) - 1).min())


def load_benchmark(path, index):
    """Lê o IFIX de um CSV com colunas date e close e devolve retornos diários.

    O IFIX não é servido pelo Yahoo. A série pode ser baixada no site da
    B3 (Índices → IFIX → Estatísticas históricas) e salva em config/ifix.csv.
    """
    frame = pd.read_csv(path, parse_dates=["date"])
    if not {"date", "close"}.issubset(frame):
        raise ValueError("O CSV do IFIX precisa das colunas date e close.")
    close = frame.drop_duplicates("date", keep="last").set_index("date").close.sort_index()
    return (close / close.shift(1) - 1).reindex(index)


def benchmark_returns(returns, ifix_path=None):
    """Retornos do índice de referência e o nome da fonte usada.

    Com config/ifix.csv, usa o IFIX. Sem ele, usa a média diária igual dos
    FIIs da amostra como substituto declarado (proxy), para não deixar o
    beta vazio. A fonte usada vai para a tabela e para o run.json.
    """
    if ifix_path and Path(ifix_path).is_file():
        return load_benchmark(ifix_path, returns.index), "IFIX (B3)"
    proxy = returns.mean(axis=1).where(returns.count(axis=1) >= max(2, returns.shape[1] // 2))
    return proxy, "proxy: média igual da amostra"


def beta(asset, market, minimum=30):
    """β = cov(ativo, índice) / var(índice), nas datas em que os dois existem."""
    joint = pd.concat([asset, market], axis=1).dropna()
    if len(joint) < minimum or joint.iloc[:, 1].var(ddof=1) <= 0:
        return np.nan
    return float(joint.iloc[:, 0].cov(joint.iloc[:, 1]) / joint.iloc[:, 1].var(ddof=1))


def fund_indicators(returns, quote, volume, profile=None, ifix_path=None):
    """Tabela consolidada com um FII por linha.

    Colunas: retorno médio diário e anualizado, volatilidade anualizada,
    drawdown máximo, volume financeiro médio (média de fechamento × volume
    nos dias com negócio), beta e, quando houver perfil, segmento, P/VP,
    DY mensal e patrimônio.
    """
    market, source = benchmark_returns(returns, ifix_path)
    turnover = (quote * volume).where(volume.gt(0))
    table = pd.DataFrame({
        "retorno_medio_diario": returns.mean(),
        "retorno_anualizado": (1 + returns.mean()) ** TRADING_DAYS - 1,
        "volatilidade_anual": returns.std(ddof=1) * np.sqrt(TRADING_DAYS),
        "drawdown_maximo": {t: max_drawdown(returns[t]) for t in returns},
        "volume_financeiro_medio_brl": turnover.reindex(columns=returns.columns).mean(),
        "beta": {t: beta(returns[t], market) for t in returns},
    })
    table["beta_referencia"] = source
    if profile is not None:
        extra = profile.reindex(table.index)[[c for c in ("segment", "p_to_book", "monthly_yield", "net_assets")
                                             if c in profile]]
        table = table.join(extra.rename(columns={"segment": "segmento", "p_to_book": "p_vp",
                                                 "monthly_yield": "dy_mensal", "net_assets": "patrimonio"}))
    table.index.name = "ticker"
    return table, source
