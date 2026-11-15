"""Coleta de cotações e informes da CVM; preparação sem preencher lacunas."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import io
import json
import zipfile

import numpy as np
import pandas as pd
import requests

CVM = "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/"
COLS = ["adjusted", "close", "volume", "dividends", "capital_gains", "splits"]
FUND = ["ticker", "cnpj", "reference", "published", "version", "segment", "name",
        "net_assets", "book_per_share", "monthly_yield", "source"]


def universe(path):
    """Lê os fundos da amostra e normaliza tickers e CNPJs."""
    # O Yahoo usa o sufixo .SA para códigos brasileiros. O CNPJ fica
    # como texto para preservar zeros à esquerda na associação com a CVM.
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "ticker" not in frame:
        raise ValueError("O CSV de amostra deve ter a coluna ticker.")
    frame["ticker"] = frame.ticker.str.strip().str.upper().map(
        lambda s: s if s.endswith(".SA") else s + ".SA")
    if not frame.ticker.str.fullmatch(r"[A-Z0-9]{4}[0-9]{2}[A-Z]?\.SA").all():
        raise ValueError("Ticker inválido na amostra.")
    if "cnpj" not in frame:
        frame["cnpj"] = ""
    frame["cnpj"] = frame.cnpj.str.replace(r"\D", "", regex=True)
    if frame.ticker.duplicated().any() or not frame.cnpj.str.fullmatch(r"\d{14}|").all():
        raise ValueError("Ticker duplicado ou CNPJ inválido na amostra.")
    return frame.sort_values("ticker").reset_index(drop=True)


def _chart(ticker, start, end):
    """Consulta o endpoint de histórico do Yahoo como alternativa ao yfinance."""
    # A API recebe segundos desde 1970. As datas de entrada são da bolsa
    # brasileira, por isso a conversão parte do fuso de São Paulo.
    def epoch(day):
        return int(pd.Timestamp(day, tz="America/Sao_Paulo").timestamp())
    resp = requests.get(YAHOO + ticker, params={"period1": epoch(start),
                        "period2": epoch(end), "interval": "1d", "events": "div,splits,capitalGains"},
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=18)
    resp.raise_for_status()
    entry = resp.json()["chart"]["result"][0]
    meta = entry["meta"]
    if meta["symbol"] != ticker or meta["currency"] != "BRL":
        raise ValueError("Identidade ou moeda divergente no Yahoo.")
    zone = meta["exchangeTimezoneName"]
    days = pd.to_datetime(entry["timestamp"], unit="s", utc=True).tz_convert(zone)
    quote = entry["indicators"]["quote"][0]
    adj = entry["indicators"]["adjclose"][0]["adjclose"]
    frame = pd.DataFrame({"adjusted": adj, "close": quote["close"], "volume": quote["volume"]}, index=days.normalize())
    for field, key in (("dividends", "dividends"), ("capital_gains", "capitalGains"), ("splits", "splits")):
        frame[field] = 0.0
        for event in entry.get("events", {}).get(key, {}).values():
            day = pd.Timestamp(event["date"], unit="s", tz="UTC").tz_convert(zone).normalize()
            if day in frame.index:
                frame.loc[day, field] = (event["numerator"] / event["denominator"]
                                         if key == "splits" else event["amount"])
    return frame


def download(ticker, start, end):
    """Busca a série de um fundo e devolve os dados e o registro de coleta."""
    import yfinance as yf

    errors = []
    # Os dois caminhos usam a mesma fonte. Se ambos falharem, o fundo
    # fica sem histórico e as tentativas ficam registradas no manifesto.
    for source in ("yfinance", "Yahoo Finance Chart"):
        try:
            if source == "yfinance":
                inst = yf.Ticker(ticker)
                hist = inst.history(start=start, end=end, interval="1d", auto_adjust=False,
                                    actions=True, keepna=True, timeout=12, raise_errors=True)
                meta = inst.history_metadata
                if meta.get("symbol") != ticker or meta.get("currency") != "BRL":
                    raise ValueError("Identidade ou moeda sem confirmação no Yahoo.")
                hist = hist.rename(columns=dict(zip(
                    ["Adj Close", "Close", "Volume", "Dividends", "Capital Gains", "Stock Splits"], COLS)))
            else:
                hist = _chart(ticker, start, end)
            if hist.empty or "adjusted" not in hist or not hist.adjusted.notna().any():
                raise ValueError("Sem histórico ajustado.")
            # Mantém preços ajustados para retornos e fechamentos para
            # indicadores em reais. Lacunas continuam como valores ausentes.
            frame = hist.reindex(columns=COLS).copy()
            idx = pd.DatetimeIndex(frame.index)
            if idx.tz is not None:
                idx = idx.tz_convert("America/Sao_Paulo").tz_localize(None)
            frame.index = idx.normalize()
            duplicates = int(frame.index.duplicated(keep="last").sum())
            frame = frame.loc[~frame.index.duplicated(keep="last")].sort_index()
            frame = frame.loc[(frame.index >= start) & (frame.index < end)]
            frame.index.name = "date"
            frame["ticker"] = ticker
            return frame.reset_index(), {"ticker": ticker, "source": source, "rows": len(frame),
                                         "duplicates_removed": duplicates, "attempt_errors": errors}
        except Exception as exc:
            errors.append(f"{source}: {type(exc).__name__}: {str(exc)[:180]}")
    return None, {"ticker": ticker, "source": None, "rows": 0, "attempt_errors": errors}


def _cvm_year(year, sample):
    """Baixa e integra os informes mensais dos fundos da amostra em um ano."""
    url = f"{CVM}inf_mensal_fii_{year}.zip"
    response = requests.get(url, timeout=35)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        def table(kind):
            with archive.open(f"inf_mensal_fii_{kind}_{year}.csv") as stream:
                return pd.read_csv(stream, encoding="latin1", sep=";", dtype=str)
        general, extra = table("geral"), table("complemento")
    # Junta a identificação do fundo aos indicadores do mesmo mês e da
    # mesma versão do informe para evitar combinar reapresentações distintas.
    keys = ["CNPJ_Fundo_Classe", "Data_Referencia", "Versao"]
    measures = {"Patrimonio_Liquido": "net_assets", "Valor_Patrimonial_Cotas": "book_per_share",
                "Percentual_Dividend_Yield_Mes": "monthly_yield"}
    for table_ in (general, extra):
        table_[keys[0]] = table_[keys[0]].str.replace(r"\D", "", regex=True)
    general = general[general[keys[0]].isin(set(sample.cnpj) - {""})]
    extra = extra[extra[keys[0]].isin(set(sample.cnpj) - {""})]
    frame = general.merge(extra[keys + list(measures)].drop_duplicates(keys, keep="last"),
                          on=keys, how="left").rename(columns={
        **measures, keys[0]: "cnpj", keys[1]: "reference", keys[2]: "version",
        "Data_Entrega": "published", "Segmento_Atuacao": "segment", "Nome_Fundo_Classe": "name"})
    frame = sample[["ticker", "cnpj"]].merge(frame, on="cnpj", how="inner")
    # CNPJ fixado na amostra e prefixo do ISIN conferido para evitar ligar outro fundo.
    has_isin = frame.Codigo_ISIN.notna()
    matches = [f"BR{t[:4]}CTF" in str(s).upper() for t, s in zip(frame.ticker, frame.Codigo_ISIN)]
    frame = frame[~has_isin | np.asarray(matches, dtype=bool)].copy()
    frame["source"] = url
    return frame[FUND]


def read_extra(path, tickers):
    """Valida uma tabela complementar com origem e data de publicação."""
    more = pd.read_csv(path, dtype={"cnpj": str, "ticker": str})
    need = {"ticker", "reference", "published", "source"}
    if not need.issubset(more) or more[list(need)].isna().any().any():
        raise ValueError(f"CSV complementar exige valores para {', '.join(sorted(need))}.")
    more["ticker"] = more.ticker.str.strip().str.upper().map(
        lambda s: s if s.endswith(".SA") else s + ".SA")
    if not set(more.ticker).issubset(tickers) or more.source.str.strip().eq("").any():
        raise ValueError("Ticker fora da amostra ou fonte vazia no CSV complementar.")
    if more[["reference", "published"]].apply(pd.to_datetime, errors="coerce").isna().any().any():
        raise ValueError("Data inválida no CSV complementar.")
    # Em caso de referência igual, a versão alta dá prioridade ao
    # complemento quando ele já estava publicado na data de corte.
    more["version"] = 1000000
    return more.reindex(columns=FUND)


def collect(sample_path, start, end, out, extra=None, workers=3, calendar_path=None):
    """Prepara o cache offline com cotações, informes e um manifesto JSON."""
    start, end = (pd.Timestamp(x).date().isoformat() for x in (start, end))
    if start >= end or workers < 1:
        raise ValueError("Período ou quantidade de trabalhadores inválida.")
    sample = universe(sample_path)
    if sample.empty:
        raise ValueError("Amostra vazia.")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda t: download(t, start, end), sample.ticker))
    frames = [f for f, _ in results if f is not None and not f.empty]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"start": start, "end_exclusive": end, "collected_utc": datetime.now(timezone.utc).isoformat(),
                "market": [m for _, m in results], "cvm_errors": {}, "files_sha256": {}}
    # Um calendário B3 externo pode detectar sessões ausentes em todos os tickers.
    # Sem ele, a união das datas observadas é a aproximação usada.
    calendar = None
    if calendar_path:
        calendar = pd.to_datetime(pd.read_csv(calendar_path)["date"], errors="raise").drop_duplicates().sort_values()
        calendar = calendar[(calendar >= start) & (calendar < end)]
        if calendar.empty:
            raise ValueError("Calendário vazio no intervalo.")
    if not frames:
        (out / "failed_collection.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        raise RuntimeError("Nenhum histórico obtido. Veja failed_collection.json.")
    fundamentals = []
    if sample.cnpj.ne("").any():
        # Um informe do ano anterior pode ser o mais recente conhecido
        # no começo do período observado.
        for year in range(int(start[:4]) - 1, int(end[:4]) + 1):
            try:
                fundamentals.append(_cvm_year(year, sample))
            except (requests.RequestException, KeyError, ValueError, zipfile.BadZipFile) as exc:
                manifest["cvm_errors"][str(year)] = f"{type(exc).__name__}: {exc}"
    if extra:
        fundamentals.append(read_extra(extra, set(sample.ticker)))
    tables = {"market.csv": pd.concat(frames, ignore_index=True), "universe.csv": sample,
              "fundamentals.csv": pd.concat(fundamentals, ignore_index=True) if fundamentals
              else pd.DataFrame(columns=FUND)}
    if calendar is not None:
        tables["calendar.csv"] = pd.DataFrame({"date": calendar})
    elif (out / "calendar.csv").exists():
        raise ValueError("Use outro diretório de cache para remover o calendário anterior.")
    # A impressão digital SHA-256 registra o conteúdo exato de cada CSV.
    # A análise verifica essas assinaturas antes de usar o cache.
    for name, table in tables.items():
        path = out / name
        table.to_csv(path, index=False)
        manifest["files_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (out / "collection.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def load_cache(path):
    """Confere a integridade e carrega as tabelas disponíveis sem usar a rede."""
    root = Path(path)
    manifest = json.loads((root / "collection.json").read_text(encoding="utf-8"))
    for name, sha in manifest["files_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:
            raise ValueError(f"Arquivo do cache alterado: {name}. Refaça a coleta.")
    market = pd.read_csv(root / "market.csv", parse_dates=["date"])
    sample = pd.read_csv(root / "universe.csv", dtype={"cnpj": str})
    fundamental = pd.read_csv(root / "fundamentals.csv", dtype={"cnpj": str})
    calendar = (pd.read_csv(root / "calendar.csv", parse_dates=["date"]).date
                if "calendar.csv" in manifest["files_sha256"] else None)
    return market, sample, fundamental, calendar, manifest


def price_panels(market, tickers, calendar=None):
    """Organiza preço ajustado, fechamento e volume em matrizes data × ticker."""
    market = market.sort_values("date", kind="stable").drop_duplicates(["date", "ticker"], keep="last")
    days = (pd.DatetimeIndex(calendar).unique().sort_values() if calendar is not None
            else pd.DatetimeIndex(market.date.unique()).sort_values())
    def panel(field):
        f = market.pivot(index="date", columns="ticker", values=field).reindex(index=days, columns=tickers)
        f.index.name = "date"
        return f.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    volume, adjusted, quote = panel("volume"), panel("adjusted"), panel("close")
    # Volume zero indica ausência de negócio; valor ausente não confirma negociação.
    traded = volume.gt(0)
    return adjusted.where(adjusted.gt(0) & traded), quote.where(quote.gt(0) & traded), volume


def apply_quarantine(prices, quotes, volume, entries):
    """Mascara as datas auditadas para cada ticker e conta os preços afetados.

    Altera cópias dos painéis de trabalho. Os CSVs originais permanecem
    disponíveis para reproduzir a auditoria.
    """
    required = ["ticker", "start", "end", "reason", "source"]
    if not set(required).issubset(entries) or entries[required].isna().any().any():
        raise ValueError("Quarentena exige ticker, start, end, reason e source.")
    entries = entries[required].copy()
    for col in ("start", "end"):
        entries[col] = pd.to_datetime(entries[col], format="%Y-%m-%d", errors="raise")
    if entries.start.gt(entries.end).any() or not set(entries.ticker).issubset(prices.columns):
        raise ValueError("Ticker ou intervalo inválido na quarentena.")
    if entries[["reason", "source"]].apply(lambda x: x.str.strip().eq("")).any().any():
        raise ValueError("Motivo e evidência são obrigatórios na quarentena.")
    prices, quotes, volume = prices.copy(), quotes.copy(), volume.copy()
    affected = []
    for row in entries.itertuples(index=False):
        mask = (prices.index >= row.start) & (prices.index <= row.end)
        affected.append(int(prices.loc[mask, row.ticker].notna().sum()))
        for panel in (prices, quotes, volume):
            panel.loc[mask, row.ticker] = np.nan
    return prices, quotes, volume, entries.assign(adjusted_rows_masked=affected)


def returns_from_prices(prices):
    """Calcula o retorno simples de um pregão para o seguinte.

    Retorno = preço ajustado de hoje / preço ajustado anterior - 1.
    Se um dos preços estiver ausente, o retorno também fica ausente.
    """
    return (prices / prices.shift(1) - 1).replace([np.inf, -np.inf], np.nan)


def assess(returns, volume, minimum, coverage, trading, quote=None, min_brl=0.0):
    """Calcula indicadores de cobertura e registra o motivo de cada exclusão."""
    if returns.empty:
        raise ValueError("Janela sem sessões.")
    rows = pd.DataFrame({"observations": returns.count(), "coverage": returns.notna().mean(),
                         "trade_fraction": volume.gt(0).mean(),
                         "median_volume": volume.where(volume.gt(0)).median(),
                         "volatility": returns.std() * np.sqrt(252)})
    rows["median_turnover_brl_proxy"] = ((volume * quote).where(volume.gt(0)).median()
                                         if quote is not None else np.nan)
    # O contador de movimentos extremos serve para auditoria. A exclusão
    # por cotação inconsistente exige um registro na tabela de quarentena.
    rows["large_move_days_abs_gt_20pct"] = returns.abs().gt(.20).sum()
    def reasons(row):
        return "; ".join(label for condition, label in [
            (row.observations < minimum, "histórico insuficiente"),
            (row.coverage < coverage, "cobertura insuficiente"),
            (row.trade_fraction < trading, "baixa frequência de negociação"),
            (min_brl > 0 and not row.median_turnover_brl_proxy >= min_brl, "giro financeiro insuficiente"),
            (not pd.notna(row.volatility) or row.volatility <= 1e-12, "sem variação mensurável")
        ] if condition)
    rows["exclusion"] = rows.apply(reasons, axis=1)
    rows["eligible"] = rows.exclusion.eq("")
    rows.index.name = "ticker"
    return rows


def snapshot(fundamentals, tickers, cutoff, quote=None):
    """Mostra os dados de cada fundo que podiam ser conhecidos até o corte."""
    frame = fundamentals.copy()
    frame["reference"] = pd.to_datetime(frame.reference, errors="coerce")
    frame["published"] = pd.to_datetime(frame.published, errors="coerce")
    frame["version"] = pd.to_numeric(frame.version, errors="coerce").fillna(0)
    cutoff = pd.Timestamp(cutoff)
    # Mês de referência e data de publicação têm papéis diferentes.
    # Uma versão entregue depois do corte fica de fora da fotografia.
    eligible = frame[(frame.published <= cutoff) & (frame.reference <= cutoff)].copy()
    snap = (eligible.sort_values(["reference", "version", "published"])
            .drop_duplicates("ticker", keep="last").set_index("ticker").reindex(tickers))
    snap.index.name = "ticker"
    snap["segment"] = snap.segment.fillna("").str.strip().replace("", "Sem classificação")
    for field in ("net_assets", "book_per_share", "monthly_yield"):
        snap[field] = pd.to_numeric(snap[field], errors="coerce")
    snap["p_to_book"] = np.nan
    snap["p_to_book_quote_date"] = pd.NaT
    if quote is not None:
        for ticker, row in snap.iterrows():
            if pd.notna(row.reference) and row.book_per_share > 0:
                # Compara o VP por cota ao último fechamento observado
                # no mesmo mês. Sem cotação naquele mês, o P/VP fica vazio.
                date = min(cutoff, row.reference + pd.offsets.MonthEnd(0))
                prices = quote.loc[:date, ticker].dropna()
                if len(prices) and prices.index[-1].to_period("M") == row.reference.to_period("M"):
                    snap.loc[ticker, "p_to_book"] = prices.iloc[-1] / row.book_per_share
                    snap.loc[ticker, "p_to_book_quote_date"] = prices.index[-1]
    return snap
