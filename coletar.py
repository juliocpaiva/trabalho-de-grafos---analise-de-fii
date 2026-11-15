"""Baixa preços ajustados de FIIs e informes mensais da CVM."""

import argparse

from fonte_yfinance import collect


def main():
    """Lê a amostra e o período solicitados e salva um cache para main.py."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amostra", default="config/amostra.csv")
    parser.add_argument("--inicio", default="2024-11-14")
    parser.add_argument("--fim", default="2026-11-14", help="Data final exclusiva.")
    parser.add_argument("--cache", default="data/coleta_api")
    args = parser.parse_args()

    # A janela inclui a data inicial e termina antes da data final.
    # A função collect guarda as respostas em CSV e registra a origem de cada série.
    try:
        coleta = collect(args.amostra, args.inicio, args.fim, args.cache)
    except (OSError, ValueError, RuntimeError) as erro:
        parser.exit(1, f"Falha na coleta: {erro}\n")

    encontrados = sum(ativo["rows"] > 0 for ativo in coleta["market"])
    print(f"Preços ajustados disponíveis para {encontrados} de {len(coleta['market'])} FIIs.")
    print(f"Dados e manifesto em {args.cache}.")
    if coleta["cvm_errors"]:
        print("Houve falhas ao baixar informes da CVM. Consulte collection.json.")


if __name__ == "__main__":
    main()
