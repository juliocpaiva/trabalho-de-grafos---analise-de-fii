# O que cada arquivo faz e retorna

[Início](../README.md) · [Checklist e pendências](estado_checklist.md)

## Fluxo de leitura

`config/amostra.csv` → `coletar.py` / `fonte_yfinance.py` → `data/coleta_api/` → `main.py` → `outputs/simples/`

Com `main.py --experimentos`: cache → `experimentos.run()` → preparação → Pearson → rede limiarizada → Louvain e Kruskal em ramos separados → comparações e carteiras → `outputs/experimentos/`.

Louvain e Kruskal são independentes na versão 1. A árvore é desenhada com as comunidades da rede. A sequência Kruskal → Louvain na árvore ainda não foi implementada.

## Arquivos Python: entrada, retorno e gravação

Os módulos auxiliares definem funções; executá-los isoladamente não gera os resultados da análise. Use `main.py`, `coletar.py` ou a CLI `fii_network`.

| Arquivo / etapa do checklist | Recebe | Faz e retorna em Python | O que grava ou mostra |
|---|---|---|---|
| [coletar.py](../coletar.py) / 1–2 | Amostra, início, fim e destino | `main()` lê opções e chama `collect()`; não retorna uma tabela ao terminal | Cache em `data/coleta_api/`; imprime disponibilidade e destino |
| [fonte_yfinance.py](../fonte_yfinance.py) / 1–3 | CSV de tickers/CNPJs; fontes Yahoo/CVM ou cache | `collect()` retorna manifesto; `load_cache()` retorna mercado, universo, fundamentos, calendário e manifesto; `price_panels()` retorna três DataFrames: ajustados, fechamentos e volumes; `apply_quarantine()` retorna os três painéis tratados e auditoria; `returns_from_prices()` retorna retornos; `assess()` retorna qualidade; `snapshot()` retorna perfil no corte | `collect()` grava os CSVs e manifesto. As funções de preparação retornam dados em memória |
| [grafo_base.py](../grafo_base.py) / 4–5 | Retornos ou matriz de correlações; limiar; perfil | `correlation()` retorna Pearson e contagens comuns; `pairs()` retorna tabela de pares; `similarity()` retorna `networkx.Graph`; `compound_similarity()` retorna matriz composta e decomposição por par; `centralities()` retorna DataFrame; `topology()` retorna dicionário | Não grava arquivos por conta própria |
| [algo_louvain.py](../algo_louvain.py) / 6 | Grafo com atributo `weight`, resolução, semente | `communities()` retorna Series ticker → comunidade e modularidade, ou `None` para modularidade sem arestas | Não grava; na versão 1 recebe a rede limiarizada |
| [algo_mst.py](../algo_mst.py) / 7 | Matriz de similaridades | `kruskal()` retorna grafo árvore/floresta, DataFrame de arestas e dicionário de validação | Não grava; não chama Louvain |
| [comparacao_modelos.py](../comparacao_modelos.py) / 5, 8, 10 parcialmente | Pearson, sobreposição, perfil, pares temporais, destino e parâmetros | `compare_models()` retorna resumo de Pearson versus peso composto | Grava `comparacao_modelos/`: comparação, pares, comunidades, árvores, GraphML e figuras opcionais; não executa E1–E4 |
| [carteiras_choques.py](../carteiras_choques.py) / complemento; 3 e 10 parcialmente | Retornos de formação/avaliação, perfil, liquidez e parâmetros | `portfolios()` retorna alocação, métricas, retornos A/B e comunidades da formação; `shocks()` retorna eventos, exposições e resumo; `metrics()` retorna métricas de carteira | Não grava; drawdown calculado aqui é de carteira |
| [experimentos.py](../experimentos.py) / integração | Cache, destino, `Settings`, opção de figuras e quarentena | `run()` executa a análise completa da versão 1 e retorna o resumo que também vai para `run.json` | CSVs, GraphML, JSON e PNGs na pasta indicada |
| [visualizacao.py](../visualizacao.py) / 9 | Matrizes, grafos, comunidades e tabelas | `heatmap()`, `network()` e `experiments()` desenham e salvam figuras; não retornam tabelas | PNGs estáticos. Cores na árvore vêm do Louvain da rede |
| [main.py](../main.py) / entrada recomendada | Cache, destino, limiar, opção `--experimentos` | `analisar()` executa o fluxo simples; `main()` escolhe simples/completo; ambos sem retorno de tabela | Resultados e resumo no terminal |
| [fii_network.py](../fii_network.py) / entrada com mais opções | Subcomandos `collect`, `analyze`, `inspect` | `main(argv)` retorna código 0 em sucesso e 2 nas falhas tratadas | Coleta, análise configurável ou perfil/pares no terminal. `inspect` lê os CSVs, sem recalcular |

## Qual pasta usar?

| Pasta | Finalidade | Como nasce |
|---|---|---|
| [config/](../config/) | Entradas editáveis: amostra, evidências B3 e intervalos de quarentena | Arquivos versionados |
| [data/coleta_api/](../data/coleta_api/) | Cache preferido por `main.py` quando há manifesto | `coletar.py` |
| [data/cache/](../data/cache/) | Cache de referência; alternativa automática de `main.py` | Coleta pela CLI ou snapshot local existente |
| [outputs/simples/](../outputs/simples/) | Visão rápida: 5 CSVs e 2 PNGs | `main.py` |
| [outputs/experimentos/](../outputs/experimentos/) | **Pasta recomendada para revisar a versão 1 completa**, incluindo comparação Pearson/composto | `main.py --experimentos` |
| [outputs/principal/](../outputs/principal/) | Execução anterior da CLI; pode ter conjunto de arquivos diferente da execução atual | Padrão de `fii_network analyze` |
| [outputs/liquidez/](../outputs/liquidez/) | Execução de referência com giro mínimo de R$ 500 mil | CLI com `--min-turnover-brl 500000` e destino separado |
| [docs/](./) | Guias, metodologia, status e notas de resultados | Documentação versionada |
| [tests/](../tests/) | Verificações com dados sintéticos: preparação, algoritmos e fluxo offline | `python -m pytest -q` |

O cache e os resultados são locais e estão ignorados pelo Git. Um link para saída só funciona após a geração nessa máquina. Rodar novamente no mesmo destino pode substituir arquivos; use `--saida` ou `--output` diferente para preservar uma execução. Compare o `run.json` de cada pasta antes de confrontar números.

## Saídas rápidas: `outputs/simples/`

| Arquivo | O que retorna para o grupo |
|---|---|
| `qualidade.csv` | Um registro por candidato: histórico, cobertura, negociação, volatilidade, elegibilidade e motivo de exclusão |
| `quarentena.csv` | Intervalos auditados e observações mascaradas |
| `correlacoes.csv` | Pearson: tickers em linhas e colunas, com sinal preservado |
| `kruskal.csv` | Arestas da árvore/floresta: fundos `a`, `b`, `rho` e `distance` |
| `fundos.csv` | Segmento, comunidade da rede e centralidades por FII; não inclui todos os indicadores da análise completa |
| `louvain.png`, `kruskal.png` | Rede e árvore, com a mesma partição como referência de cores |

## Saídas completas: `outputs/experimentos/`

| Arquivo(s) | Conteúdo e interpretação |
|---|---|
| `run.json` | Parâmetros, versões, fontes, janela, métricas de rede/árvore, estado dos experimentos e limitações; ponto de partida para auditar a execução |
| `quality.csv` | Qualidade no período inteiro; `eligible` informa inclusão e `exclusion` explica rejeição |
| `quality_formation.csv`, `quality_test.csv` | Qualidade calculada separadamente antes e depois do corte |
| `formation_metadata.csv` | Fotografia de fundamentos disponíveis até o corte de formação |
| `fund_profiles.csv` | Um FII elegível por linha: segmento, fundamentos, qualidade, comunidade e centralidades |
| `returns.csv` | Retornos diários dos elegíveis: datas nas linhas e tickers nas colunas |
| `correlations.csv`, `overlap.csv` | Pearson e número de retornos válidos em comum por par; não contêm Spearman |
| `pairs.csv` | Todos os pares distintos, `rho` decrescente, sobreposição, atributos dos dois fundos, mesmo segmento/comunidade e inclusão na rede |
| `similarity_edges.csv` | Apenas pares que passaram pelo limiar; permite conferir a rede sem a redução visual de arestas |
| `segment_communities.csv` | Contagens de fundos por segmento e comunidade |
| `communities.csv` | Resumo por comunidade: quantidade de fundos/segmentos e correlação interna; atribuição por ticker está em `fund_profiles.csv` |
| `community_pair_correlations.csv` | Quantidade e média de correlações dentro/entre comunidades |
| `centralities.csv` | Grau (`degree`), força (`strength`) e intermediação (`betweenness`) por FII |
| `kruskal_edges.csv` | Arestas escolhidas, correlação original e distância |
| `similarity.graphml`, `kruskal.graphml` | Rede limiarizada e árvore/floresta com atributos, para programas como Gephi |
| `sensitivity.csv`, `sensitivity_members.csv` | Métricas por limiar/resolução e comunidade de cada fundo em cada configuração |
| `temporal_members.csv`, `temporal_pairs.csv` | Comunidades e correlações em duas janelas; resumo de estabilidade em `run.json` → `temporal` |
| `portfolios.csv` | Fundos, ordem de seleção, pesos e grupos das carteiras A/B |
| `portfolio_metrics.csv`, `portfolio_returns.csv` | Métricas e séries diárias A/B no período de avaliação; métricas de carteiras não são indicadores individuais dos FIIs |
| `shock_dates.csv`, `shock_exposures.csv` | Datas do gatilho de choque e associação de retornos dos grupos/carteiras com esses dias |
| `price_quarantine.csv` | Intervalos auditados aplicados naquela execução, se a quarentena foi informada |
| `matriz_correlacao.png` | Mapa de calor de Pearson |
| `rede_louvain.png`, `estrutura_kruskal.png` | Rede com comunidades e árvore com as mesmas cores |
| `segmentos_comunidades.png`, `centralidade.png` | Composição por segmento e ranking de centralidade |
| `sensibilidade.png`, `estabilidade.png` | Mudanças com parâmetros e entre janelas |
| `carteiras.png`, `choques.png` | Comparação A/B e co-movimentos em dias de choque |

Carteiras e choques podem não produzir todas as tabelas por insuficiência de dados. Leia o estado em `run.json`; a pasta pode conter arquivos de uma execução anterior se tiver sido reutilizada.

### Subpasta `comparacao_modelos/`

Esta comparação é **Pearson versus composto da consultoria**, não proporcional versus inverso do checklist.

| Arquivo(s) | Conteúdo |
|---|---|
| `comparacao.csv` | Uma linha por modelo: vértices, arestas, comunidades, modularidade, ligações entre segmentos e custo de Kruskal |
| `pares.csv` | Pearson, segmentos, patrimônios, faixas e parcelas do peso composto; também indica aresta em cada rede |
| `comunidades.csv` | Comunidade por ticker em cada modelo |
| `kruskal_pearson.csv`, `kruskal_composto.csv` | Arestas escolhidas e distâncias; coluna `peso` evita confundir composto com Pearson |
| `rede_pearson.graphml`, `rede_composto.graphml` | Redes limiarizadas completas para inspeção externa |
| `rede_pearson.png`, `rede_composto.png`, `kruskal_composto.png` | Figuras das redes e da árvore composta |
| `caso_entre_segmentos.csv`, `caso_entre_segmentos.png` | Par ilustrativo de segmentos distintos e seu comportamento entre janelas, quando disponível |

### Campos que mais geram dúvida

| Campo | Significado |
|---|---|
| `rho` | Correlação de Pearson em [-1, 1] |
| `overlap` / `pregoes_em_comum` | Quantidade de datas válidas em comum, não intensidade de correlação |
| `weight` | Força da ligação no modelo usado; na rede Pearson é a própria correlação positiva |
| `distance` | Dissimilaridade de Kruskal: `sqrt(2*(1-peso))`; menor valor entra primeiro |
| `cost` | Custo de caminhos da centralidade: `round(1e6/rho)`; não é o modelo inverso da distância |
| `community` | Rótulo calculado por Louvain; o número não é ranking e não deve ser comparado diretamente entre execuções |
| `segment` | Classificação da CVM, não comunidade detectada |
| `monthly_yield` | DY mensal em fração; `0.01` equivale a 1% |
| `volatility` | Desvio-padrão diário anualizado por raiz de 252, em fração |
| `median_turnover_brl_proxy` | Mediana de fechamento × volume, em reais; não volume financeiro médio |

## Documentos e testes

| Arquivo | Para que abrir |
|---|---|
| [estado_checklist.md](estado_checklist.md) | Conferir cada item do PDF e as lacunas atuais |
| [matriz_requisitos.md](matriz_requisitos.md) | Rastrear o escopo original às diretrizes registradas em 15/11 |
| [metodologia.md](metodologia.md) | Entender fórmulas, hipóteses, fontes e limitações |
| [resultados_referencia.md](resultados_referencia.md) | Ler números e interpretação da execução histórica, sem confundir com uma nova execução |
| [roteiro_demonstracao.md](roteiro_demonstracao.md) | Apresentar a versão 1 em cerca de 15 minutos |
| [responsabilidades.md](responsabilidades.md) | Preencher nomes e contribuições confirmadas pelo grupo |
| [guia_tecnico_v1.md](guia_tecnico_v1.md) | Consultar o README anterior, preservado como referência histórica |
| [test_data_graph.py](../tests/test_data_graph.py), [test_analysis.py](../tests/test_analysis.py) | Conferir propriedades de preparação, grafos e fluxo de análise |
