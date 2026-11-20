"""Comandos de coleta, análise offline e consulta de um fundo."""
import argparse
from pathlib import Path
import sys

import pandas as pd

from experimentos import Settings, run
from fonte_yfinance import collect


def parser():
    """Define os comandos complementares de coleta, análise e consulta."""
    p = argparse.ArgumentParser(prog="fii-network", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    source = sub.add_parser("collect", help="baixar dados públicos para cache local")
    source.add_argument("--sample", default="config/amostra.csv")
    source.add_argument("--start", default="2024-11-14")
    source.add_argument("--end", default="2026-11-14", help="data final exclusiva")
    source.add_argument("--cache", default="data/cache")
    source.add_argument("--fundamentals", help="CSV complementar com referência, publicação e fonte")
    source.add_argument("--calendar", help="CSV de sessões B3 com coluna date")
    source.add_argument("--workers", type=int, default=3)
    model = sub.add_parser("analyze", help="executar experimentos offline")
    model.add_argument("--cache", default="data/cache")
    model.add_argument("--output", default="outputs/principal")
    model.add_argument("--cutoff", default="2025-11-14", help="última data permitida na formação")
    model.add_argument("--tau", type=float, default=.35)
    model.add_argument("--thresholds", type=float, nargs="+", default=[.20, .35, .50, .65])
    model.add_argument("--resolution", type=float, default=1)
    model.add_argument("--resolutions", type=float, nargs="+", default=[.75, 1.0, 1.25])
    model.add_argument("--seed", type=int, default=42)
    model.add_argument("--min-days", type=int, default=90)
    model.add_argument("--min-overlap", type=int, default=75)
    model.add_argument("--coverage", type=float, default=.80)
    model.add_argument("--trading", type=float, default=.80)
    model.add_argument("--min-turnover-brl", type=float, default=0, help="mediana mínima de fechamento × volume")
    model.add_argument("--portfolio-size", type=int, default=6)
    model.add_argument("--min-test-days", type=int, default=60)
    model.add_argument("--shock-segment", help="nome exato do segmento nas tabelas CVM")
    model.add_argument("--shock-quantile", type=float, default=.05)
    model.add_argument("--shock-threshold", type=float, help="retorno negativo em fração, ex.: -0.02")
    model.add_argument("--min-events", type=int, default=5)
    model.add_argument("--quarantine", help="CSV de intervalos de preços inválidos com evidência")
    model.add_argument("--no-figures", action="store_true")
    inspect = sub.add_parser("inspect", help="consultar perfil e pares de um FII")
    inspect.add_argument("ticker")
    inspect.add_argument("--output", default="outputs/principal")
    inspect.add_argument("--top", type=int, default=10)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "collect":
            info = collect(args.sample, args.start, args.end, args.cache, args.fundamentals,
                           args.workers, args.calendar)
            found = sum(x["rows"] > 0 for x in info["market"])
            print(f"Histórico disponível: {found}/{len(info['market'])} tickers. Cache: {args.cache}")
            if info["cvm_errors"]:
                print("Alguns arquivos CVM falharam; consulte collection.json.")
        elif args.command == "analyze":
            # Separa os caminhos e opções de saída dos parâmetros usados
            # no estudo. Settings recebe somente os parâmetros do modelo.
            opts = vars(args).copy()
            cache, output, figures = opts.pop("cache"), opts.pop("output"), not opts.pop("no_figures")
            opts.pop("command")
            quarantine = opts.pop("quarantine")
            result = run(cache, output, Settings(**opts), figures, quarantine)
            print(f"{result['eligible_assets']}/{result['candidate_assets']} FIIs elegíveis; "
                  f"{result['graph']['communities']} comunidades, {result['kruskal']['edges']} arestas em Kruskal.")
            print(f"Carteiras: {result['portfolios']}. Choque: {result['shock']['status']}. Saídas: {output}")
        else:
            ticker = args.ticker.strip().upper().removesuffix(".SA") + ".SA"
            root = Path(args.output)
            funds = pd.read_csv(root / "fund_profiles.csv", dtype={"cnpj": str}).set_index("ticker")
            if ticker not in funds.index or args.top < 1:
                raise ValueError("Ticker não elegível no resultado ou quantidade de pares inválida.")
            pairs = pd.read_csv(root / "pairs.csv")
            print(funds.loc[ticker].to_string())
            print(pairs.loc[pairs.a.eq(ticker) | pairs.b.eq(ticker),
                            ["a", "b", "rho", "overlap", "same_segment", "same_community"]]
                  .head(args.top).to_string(index=False))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
