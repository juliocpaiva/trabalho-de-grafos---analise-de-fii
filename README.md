# SMAC03 — Rede de similaridade entre FIIs

Protótipo em Python para o Cenário 1 de Grafos (UNIFEI, 2026.2). Investiga se correlações de retornos revelam concentrações que não aparecem na divisão por segmentos.

O grafo principal liga fundos com correlação positiva acima de um limiar. Louvain detecta comunidades nessa rede. Kruskal extrai uma estrutura mínima de um segundo grafo, que usa todos os pares com correlação estimável. A aplicação também compara duas carteiras em um período posterior ao da seleção e mede como elas se comportaram em dias de queda de um segmento.

## Rodar os dois programas

Abra o terminal do VS Code em `D:\fii` e rode:

```powershell
.\.venv\Scripts\python.exe coletar.py
.\.venv\Scripts\python.exe main.py
```

`coletar.py` baixa preços ajustados via yfinance e informes da CVM. `main.py` usa os dados salvos em `data/coleta_api` ou o cache de referência em `data/cache` se a coleta ainda não foi feita. Com um cache disponível, você pode abrir o terminal e executar só `main.py`, inclusive offline.

Para rodar também os estudos de carteiras, sensibilidade e choques, execute `.\.venv\Scripts\python.exe main.py --experimentos`. Os resultados completos vão para `outputs/experimentos`.

A análise calcula retornos e correlações, agrupa os FIIs por Louvain e usa Kruskal para ligar os fundos com a menor soma de distâncias. As saídas em `outputs/simples` incluem a lista das arestas selecionadas, a matriz de correlações, o perfil dos fundos e dois gráficos. Edite `config/amostra.csv` para mudar os FIIs ou rode `main.py --limiar 0.45` para mudar o corte de correlação.

## Experimentos adicionais

Use Python 3.11 ou superior. Para repetir com o ambiente já montado neste workspace, comece pela linha que define `$fiiPython`.

```powershell
python -m venv .venv
$fiiPython = '.\.venv\Scripts\python.exe'
& $fiiPython -m pip install -e '.[test]'
& $fiiPython -m pytest -q
```

A coleta exige internet. A execução de referência já possui cache local, portanto pode começar em `analyze` e rodar sem conexão.

```powershell
& $fiiPython -m fii_network collect --start 2024-11-14 --end 2026-11-14
& $fiiPython -m fii_network analyze --cutoff 2025-11-14 --shock-segment Shoppings --quarantine config/quarentena_precos.csv
& $fiiPython -m fii_network inspect VISC11 --top 5
& $fiiPython -m fii_network analyze --shock-segment Shoppings --quarantine config/quarentena_precos.csv --min-turnover-brl 500000 --output outputs/liquidez
```

O término da coleta é exclusivo. Nas duas execuções de referência, `--quarantine` aplica os intervalos confirmados por [cotações oficiais da B3](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/). O CSV `config/auditoria_b3.csv` guarda as 11 discrepâncias e as fontes; o cache bruto é mantido. Use `--help` em cada comando para ajustar amostra, janela, elegibilidade, limiar, resolução, semente, tamanho da carteira e corte de choque. Use outro diretório de saída para cada configuração que quiser preservar.

## Onde encontrar cada resultado

| Caminho                                                                                          | Conteúdo                                                                                        |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `data/cache/`                                                                                  | Preços, volumes, eventos, informes e manifesto de coleta com SHA-256.                           |
| `outputs/principal/run.json`                                                                   | Configuração, versões, cobertura, métricas e limitações.                                   |
| `outputs/principal/{quality,fund_profiles,pairs,price_quarantine}.csv`                         | Elegibilidade, fundamentos e consulta de pares.                                                  |
| `outputs/principal/{correlations,overlap,segment_communities,community_pair_correlations}.csv` | Pearson com sinal, datas em comum, composição e correlações entre comunidades.               |
| `outputs/principal/{similarity,kruskal}.graphml`                                               | Grafos com atributos, importáveis em ferramentas como Gephi.                                    |
| `outputs/principal/{portfolio_metrics,portfolios,portfolio_returns}.csv`                       | Métricas, composição e retornos das carteiras.                                                |
| `outputs/principal/{shock_dates,shock_exposures,sensitivity,temporal_pairs}.csv`               | Choques, sensibilidade e estabilidade entre janelas.                                             |
| `outputs/principal/*.png`                                                                      | Nove figuras: correlações, dois grafos, composição, centralidade e experimentos.             |
| `docs/`                                                                                        | Matriz, metodologia, resultados de referência, roteiro de demonstração e registro de papéis. |

## Código

Os arquivos Python ficam lado a lado na raiz, como no trabalho de referência.

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Lê o cache e chama as etapas da análise. |
| `coletar.py` e `fonte_yfinance.py` | Baixam e preparam dados do Yahoo Finance e da CVM. |
| `grafo_base.py` | Calcula Pearson, monta o grafo e calcula centralidades. |
| `algo_mst.py` | Implementa Kruskal com união de conjuntos. |
| `algo_louvain.py` | Calcula comunidades e modularidade. |
| `experimentos.py` e `carteiras_choques.py` | Executam os estudos adicionais. |
| `visualizacao.py` | Gera os gráficos. |
| `fii_network.py` | Mantém os comandos opcionais da versão anterior. |

Fontes de preços e eventos: [Yahoo Finance por yfinance](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html). Fonte de classificação e fundamentos: [Informes Mensais Estruturados da CVM](https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal). `config/amostra.csv` documenta o universo de conveniência e o vínculo ticker–CNPJ. A coleta tenta primeiro yfinance e, se necessário, consulta o endpoint de séries do mesmo provedor. O manifesto guarda falhas e origem por ticker. Há suporte a `--fundamentals arquivo.csv`; use `ticker,reference,published,source` e, quando disponíveis, `cnpj,segment,name,net_assets,book_per_share,monthly_yield`. Cada linha é um registro completo desse fundo na data indicada; campos ausentes permanecem vazios. `monthly_yield` está em fração. Um CSV de calendário com coluna `date` pode ser informado com `--calendar`.
