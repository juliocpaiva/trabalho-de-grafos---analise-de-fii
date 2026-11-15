"""Monta a rede de FIIs e calcula a árvore geradora mínima."""

import argparse
from pathlib import Path

import pandas as pd

from algo_louvain import communities
from algo_mst import kruskal
from fonte_yfinance import (
    apply_quarantine,
    assess,
    load_cache,
    price_panels,
    returns_from_prices,
    snapshot,
)
from grafo_base import centralities, correlation, similarity
from visualizacao import network


def analisar(cache, saida, limiar):
    """Lê os dados salvos e exporta os grafos, as tabelas e os gráficos."""
    # O cache guarda as observações baixadas por coletar.py. Cada painel abaixo
    # usa pregões nas linhas e tickers nas colunas para alinhar os fundos.
    mercado, amostra, informes, calendario, _ = load_cache(cache)
    precos, fechamentos, volumes = price_panels(mercado, amostra.ticker.tolist(), calendario)
    # As datas auditadas na B3 ficam vazias, preservando a série bruta no cache.
    quarentena = pd.read_csv("config/quarentena_precos.csv")
    quarentena = quarentena[quarentena.ticker.isin(precos.columns)]
    precos, fechamentos, volumes, auditoria = apply_quarantine(
        precos, fechamentos, volumes, quarentena
    )

    # Um fundo elegível precisa de 90 retornos válidos, cobertura de pelo
    # menos 80% dos pregões e observação de negócio em pelo menos 80%.
    retornos = returns_from_prices(precos)
    qualidade = assess(retornos, volumes, minimum=90, coverage=0.80, trading=0.80)
    tickers = qualidade.index[qualidade.eligible]
    if len(tickers) < 2:
        raise ValueError("São necessários pelo menos dois FIIs com histórico suficiente.")

    # Cada par precisa de 75 retornos na mesma data. Louvain recebe a rede
    # com pesos de Pearson positivos que atingiram o limiar (0,35 por padrão).
    matriz, _ = correlation(retornos[tickers], min_overlap=75)
    rede = similarity(matriz, limiar)
    grupos, modularidade = communities(rede, seed=42)
    # Kruskal usa a matriz inteira. Até correlações negativas podem ajudar
    # a ligar componentes quando faltarem alternativas de menor distância.
    arvore, arestas, resumo = kruskal(matriz)
    # O segmento vem do informe mais recente disponível no fim da janela.
    # Unimos a classificação, a comunidade e as centralidades pelo ticker.
    segmentos = snapshot(informes, list(tickers), precos.index.max())["segment"]
    perfil = segmentos.to_frame().join(grupos).join(centralities(rede))

    saida.mkdir(parents=True, exist_ok=True)
    qualidade.to_csv(saida / "qualidade.csv")
    auditoria.to_csv(saida / "quarentena.csv", index=False)
    matriz.to_csv(saida / "correlacoes.csv")
    arestas.to_csv(saida / "kruskal.csv", index=False)
    perfil.to_csv(saida / "fundos.csv")
    network(arvore, grupos, saida, "kruskal", "Estrutura mínima de Kruskal", seed=42)
    network(rede, grupos, saida, "louvain", "Rede de similaridade dos FIIs", seed=42)

    estrutura = "árvore" if resumo["connected"] else "floresta"
    print(f"{len(tickers)} FIIs elegíveis, {rede.number_of_edges()} relações e {grupos.nunique()} comunidades.")
    if modularidade is not None:
        print(f"Modularidade: {modularidade:.3f}.")
    print(f"Kruskal: {estrutura} com {resumo['edges']} arestas e distância total {resumo['total_distance']:.3f}.")
    print(f"Resultados em {saida}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, help="Pasta com os dados de coletar.py.")
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--experimentos", action="store_true", help="Executa a análise completa, incluindo carteiras e choques.")
    parser.add_argument("--limiar", type=float, default=0.35)
    args = parser.parse_args()

    # Prefere a última coleta local. O cache de referência permite abrir o
    # projeto e usar main.py antes de rodar coletar.py.
    cache_api = Path("data/coleta_api")
    cache = args.cache or (cache_api if (cache_api / "collection.json").is_file() else Path("data/cache"))
    try:
        if args.experimentos:
            from experimentos import Settings, run

            saida = args.saida or Path("outputs/experimentos")
            # Até o corte inclusive são dados de formação. Os pregões
            # posteriores são reservados para avaliar as carteiras.
            parametros = Settings(cutoff="2025-11-14", tau=args.limiar, shock_segment="Shoppings")
            resumo = run(cache, saida, parametros, quarantine="config/quarentena_precos.csv")
            print(f"Carteiras: {resumo['portfolios']}. Choque: {resumo['shock']['status']}.")
            print(f"Resultados completos em {saida}.")
        else:
            analisar(cache, args.saida or Path("outputs/simples"), args.limiar)
    except FileNotFoundError as erro:
        parser.exit(1, f"Arquivo ausente: {erro.filename}. Execute coletar.py para baixar os dados.\n")
    except (OSError, ValueError, RuntimeError) as erro:
        parser.exit(1, f"Falha na análise: {erro}\n")


if __name__ == "__main__":
    main()
