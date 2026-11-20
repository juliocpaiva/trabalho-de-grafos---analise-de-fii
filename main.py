"""Monta a rede de FIIs e calcula a árvore geradora mínima."""

import argparse
from pathlib import Path
import sys
import webbrowser

import pandas as pd

import dashboard
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
from grafo_base import centralities, correlation, signed_pairs, signed_similarity
from visualizacao import network


RAIZ = Path(__file__).resolve().parent
QUARENTENA = RAIZ / "config" / "quarentena_precos.csv"
IFIX = RAIZ / "config" / "ifix.csv"


def open_dashboard(path):
    """Abre o painel local no navegador padrão ou informa o caminho manual."""
    dashboard_path = Path(path).resolve()
    if not webbrowser.open(dashboard_path.as_uri(), new=2):
        print(f"Não foi possível abrir o navegador automaticamente: {dashboard_path}", file=sys.stderr)


def analisar(cache, saida, limiar):
    """Lê os dados salvos e exporta os grafos, as tabelas e os gráficos."""
    # O cache guarda as observações baixadas por coletar.py. Cada painel abaixo
    # usa pregões nas linhas e tickers nas colunas para alinhar os fundos.
    mercado, amostra, informes, calendario, _ = load_cache(cache)
    precos, fechamentos, volumes = price_panels(mercado, amostra.ticker.tolist(), calendario)
    # As datas auditadas na B3 ficam vazias, preservando a série bruta no cache.
    quarentena = pd.read_csv(QUARENTENA)
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
    matriz, sobreposicao = correlation(retornos[tickers], min_overlap=75)
    rede, rede_inversa = signed_similarity(matriz, limiar, sobreposicao)
    grupos, modularidade = communities(rede, seed=42)
    grupos_inversos, modularidade_inversa = communities(rede_inversa, seed=42)
    # Kruskal usa a matriz inteira. Até correlações negativas podem ajudar
    # a ligar componentes quando faltarem alternativas de menor distância.
    arvore, arestas, resumo = kruskal(matriz)
    # O segmento vem do informe mais recente disponível no fim da janela.
    # Unimos a classificação, a comunidade e as centralidades pelo ticker.
    segmentos = snapshot(informes, list(tickers), precos.index.max())["segment"]
    perfil = (segmentos.to_frame().join(grupos)
              .join(grupos_inversos.rename("inverse_community")).join(centralities(rede)))
    perfil["direct_community"] = perfil["community"]
    pares_assinados = signed_pairs(matriz, sobreposicao, limiar)
    pares_diretos = pares_assinados[pares_assinados.relation.eq("direta")]
    pares_inversos = pares_assinados[pares_assinados.relation.eq("inversa")]

    saida.mkdir(parents=True, exist_ok=True)
    qualidade.to_csv(saida / "qualidade.csv")
    auditoria.to_csv(saida / "quarentena.csv", index=False)
    matriz.to_csv(saida / "correlacoes.csv")
    sobreposicao.to_csv(saida / "sobreposicao.csv")
    arestas.to_csv(saida / "kruskal.csv", index=False)
    pares_assinados.to_csv(saida / "arestas_assinadas.csv", index=False)
    pares_diretos.to_csv(saida / "arestas_diretas.csv", index=False)
    pares_inversos.to_csv(saida / "arestas_inversas.csv", index=False)
    perfil.to_csv(saida / "fundos.csv")
    network(arvore, grupos, saida, "kruskal", "Estrutura mínima de Kruskal", seed=42)
    network(rede, grupos, saida, "louvain", "Rede de similaridade dos FIIs", seed=42)
    network(rede_inversa, grupos_inversos, saida, "louvain_inversa",
            "Rede de relações inversas dos FIIs", seed=42)
    dashboard.write_dashboard(saida, {
        "settings": {"tau": limiar, "resolution": 1.0, "seed": 42, "min_overlap": 75},
        "relations": {
            "direct": dashboard.relation_payload(
                rede, grupos, modularidade, segmentos.fillna("").to_dict()),
            "inverse": dashboard.relation_payload(
                rede_inversa, grupos_inversos, modularidade_inversa, segmentos.fillna("").to_dict()),
        },
    })

    estrutura = "árvore" if resumo["connected"] else "floresta"
    print(f"{len(tickers)} FIIs elegíveis; {rede.number_of_edges()} relações diretas em "
          f"{grupos.nunique()} comunidades e {rede_inversa.number_of_edges()} relações inversas em "
          f"{grupos_inversos.nunique()} comunidades.")
    if modularidade is not None:
        print(f"Modularidade direta: {modularidade:.3f}.")
    if modularidade_inversa is None:
        print("Modularidade inversa: indefinida (nenhuma aresta atingiu o limiar).")
    else:
        print(f"Modularidade inversa: {modularidade_inversa:.3f}.")
    print(f"Kruskal: {estrutura} com {resumo['edges']} arestas e distância total {resumo['total_distance']:.3f}.")
    print(f"Painel interativo em {saida / 'dashboard.html'}.")
    print(f"Resultados em {saida}.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, help="Pasta com os dados de coletar.py.")
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--experimentos", action="store_true", help="Executa a análise completa, incluindo carteiras e choques.")
    parser.add_argument("--limiar", type=float, default=0.35)
    parser.add_argument("--repeticoes", type=int, default=30,
                        help="Repetições de cada experimento E1–E4 para medir tempo e estabilidade.")
    parser.add_argument("--sem-navegador", action="store_true", help="Não abre o painel ao terminar.")
    args = parser.parse_args(argv)

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
            parametros = Settings(cutoff="2025-11-14", tau=args.limiar, shock_segment="Shoppings",
                                  protocol_repeats=args.repeticoes, ifix_path=str(IFIX))
            resumo = run(cache, saida, parametros, quarantine=str(QUARENTENA))
            if not args.sem_navegador:
                open_dashboard(resumo["dashboard"])
            vencedores = resumo["protocolo_e1_e4"]["vencedores"]
            print(f"E1–E4: melhor qualidade {', '.join(vencedores['melhor_qualidade'])}; "
                  f"melhor equilíbrio {', '.join(vencedores['melhor_equilibrio'])}.")
            print(f"Carteiras: {resumo['portfolios']}. Choque: {resumo['shock']['status']}.")
            comparacao = resumo["comparacao_modelos"]
            print(f"Comparação entre modelos: {comparacao['status']} ({comparacao['compared_funds']} FIIs).")
            print(f"Painel interativo em {resumo['dashboard']}.")
            print(f"Resultados completos em {saida}.")
        else:
            saida = args.saida or Path("outputs/simples")
            analisar(cache, saida, args.limiar)
            if not args.sem_navegador:
                open_dashboard(saida / "dashboard.html")
    except FileNotFoundError as erro:
        parser.exit(1, f"Arquivo ausente: {erro.filename}. Execute coletar.py para baixar os dados.\n")
    except (OSError, ValueError, RuntimeError) as erro:
        parser.exit(1, f"Falha na análise: {erro}\n")


if __name__ == "__main__":
    main()
