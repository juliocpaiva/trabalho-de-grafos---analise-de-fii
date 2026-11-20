# Checklist do grupo: o que existe e o que falta

> **Atualização de 20/11/2026:** este documento descreve a versão 1. Spearman, pesos do grafo completo, Louvain na árvore, protocolo E1–E4 e indicadores por FII foram implementados depois; o estado atual está na seção Pendências do [README](../README.md).

Revisão do código e das saídas locais em **18/11/2026**, usando os dez itens de `Checklist trabalho grafos.pdf`, enviado pelo grupo. Este documento organiza a versão 1; não implementa os experimentos novos do checklist.

**Desenvolvido** = há implementação para o subitem descrito. **Parcial** = há parte ou uma variante, com a diferença indicada. **Pendente** = não foi encontrada implementação. A existência de uma função não garante dados disponíveis para todos os fundos. Os resultados numéricos históricos estão em [resultados de referência](resultados_referencia.md).

As diretrizes acadêmicas registradas na [matriz original](matriz_requisitos.md) e o checklist do grupo são referências diferentes. Os antigos registros de “verificado” dizem respeito ao escopo anterior, não à conclusão deste checklist.

## Visão geral

| Etapa do PDF | Estado da etapa | Código principal | Resultado para abrir primeiro |
|---|---|---|---|
| [1. Seleção dos FIIs](#etapa-1) | Parcial | [fonte_yfinance.py](../fonte_yfinance.py) | [quality.csv](../outputs/experimentos/quality.csv) |
| [2. Coleta histórica](#etapa-2) | Desenvolvido, sujeito à disponibilidade da fonte | [coletar.py](../coletar.py) | [collection.json](../data/coleta_api/collection.json) |
| [3. Indicadores financeiros](#etapa-3) | Parcial | [fonte_yfinance.py](../fonte_yfinance.py) | [fund_profiles.csv](../outputs/experimentos/fund_profiles.csv) |
| [4. Correlações](#etapa-4) | Parcial: Pearson | [grafo_base.py](../grafo_base.py) | [correlations.csv](../outputs/experimentos/correlations.csv) |
| [5. Grafos e pesos](#etapa-5) | Parcial: rede limiarizada e distâncias | [grafo_base.py](../grafo_base.py) | [similarity_edges.csv](../outputs/experimentos/similarity_edges.csv) |
| [6. Louvain direto](#etapa-6) | Parcial: na rede limiarizada | [algo_louvain.py](../algo_louvain.py) | [fund_profiles.csv](../outputs/experimentos/fund_profiles.csv) |
| [7. Kruskal + Louvain](#etapa-7) | Parcial: Kruskal; Louvain na árvore pendente | [algo_mst.py](../algo_mst.py) | [kruskal_edges.csv](../outputs/experimentos/kruskal_edges.csv) |
| [8. Comparação E1–E4](#etapa-8) | Parcial: existem outras comparações | [comparacao_modelos.py](../comparacao_modelos.py) | [comparacao.csv](../outputs/experimentos/comparacao_modelos/comparacao.csv) |
| [9. Visualizações](#etapa-9) | Parcial | [visualizacao.py](../visualizacao.py) | [rede_louvain.png](../outputs/experimentos/rede_louvain.png) |
| [10. Análise acadêmica](#etapa-10) | Parcial | [metodologia](metodologia.md) | [resultados de referência](resultados_referencia.md) |

Os links de resultados acima apontam para arquivos gerados localmente. Em uma cópia nova do Git, gere-os antes pelo comando do [README](../README.md); `data/cache/`, `data/coleta_api/` e `outputs/` estão no `.gitignore`.

<a id="etapa-1"></a>
## 1. Seleção dos FIIs brasileiros

| Subitem do checklist | Estado | Onde conferir / limite |
|---|---|---|
| Definir a fonte da lista | Parcial | [amostra.csv](../config/amostra.csv) contém 42 tickers e CNPJs; a metodologia declara amostra intencional. Falta documentar a procedência oficial da lista como universo B3/CVM/IFIX. |
| Obter lista de tickers | Desenvolvido | `fonte_yfinance.universe()` lê a amostra; não descobre automaticamente todos os FIIs. |
| Validar FIIs negociados na B3 | Parcial | Validação de formato, CNPJ e vínculo com informes CVM; auditoria B3 pontual em [auditoria_b3.csv](../config/auditoria_b3.csv). Falta validação cadastral oficial de toda a amostra. |
| Adicionar `.SA` | Desenvolvido | `universe()` normaliza os tickers. |
| Definir período histórico | Desenvolvido | `coletar.py`: 14/11/2024 até antes de 14/11/2026 por padrão. |
| Definir mínimo de histórico | Desenvolvido | `assess()`: 90 retornos, cobertura de 80% no padrão. |
| Definir mínimo de liquidez | Desenvolvido | Negociação em 80% das sessões; giro financeiro opcional na CLI completa. O padrão não impõe valor mínimo em reais. |
| Selecionar elegíveis e registrar exclusões | Desenvolvido | `assess()`; `quality.csv`: `eligible` e `exclusion`, inclusive candidatos sem histórico. |

<a id="etapa-2"></a>
## 2. Coleta dos dados históricos

| Subitem do checklist | Estado | Onde conferir / limite |
|---|---|---|
| Instalar/configurar yfinance | Desenvolvido | Dependência em [pyproject.toml](../pyproject.toml); instalação no README. |
| Consultar preços e preços ajustados | Desenvolvido | `fonte_yfinance.download()`; [market.csv](../data/coleta_api/market.csv): `close` e `adjusted`. Há alternativa no endpoint de séries do mesmo provedor. |
| Obter volumes e dividendos quando disponíveis | Desenvolvido | `market.csv`: `volume`, `dividends`, `splits` e `capital_gains`. Ausência na fonte continua sendo uma limitação. |
| Conferir disponibilidade por fundo | Desenvolvido | `collection.json`: linhas e falhas por ticker; `quality.csv`: cobertura efetiva. |
| Alinhar datas | Desenvolvido | `price_panels()`: painéis por sessão e ticker; calendário informado ou união de datas observadas. Não equivale a um calendário oficial B3 obrigatório. |
| Tratar ausências e inconsistências | Desenvolvido | `price_panels()`, `apply_quarantine()` e `returns_from_prices()`. Não preenche preços faltantes; preserva o cache bruto. |
| Salvar base histórica em CSV | Desenvolvido | `collect()`: `market.csv`, `universe.csv`, `fundamentals.csv` e manifesto. |

<a id="etapa-3"></a>
## 3. Tratamento e indicadores financeiros

| Subitem do checklist | Estado | Onde conferir / limite |
|---|---|---|
| Retornos diários | Desenvolvido | `returns_from_prices()`; [returns.csv](../outputs/experimentos/returns.csv). Valores em fração. |
| Retorno médio de cada fundo | Pendente | Existem retornos diários; falta a coluna consolidada por FII. |
| Volatilidade | Desenvolvido | `assess()`; `quality.csv` e `fund_profiles.csv`: `volatility`, anualizada por raiz de 252. |
| Drawdown máximo de cada fundo | Parcial | `carteiras_choques.metrics()` calcula para carteiras A/B, em `portfolio_metrics.csv`; falta por FII. |
| Beta em relação ao IFIX | Pendente | Não há série do IFIX nem cálculo de beta. |
| Volume financeiro médio | Parcial | `median_turnover_brl_proxy` é a **mediana** de fechamento × volume, não a média solicitada. |
| Dividend Yield | Desenvolvido com cobertura variável | `snapshot()`; `monthly_yield` vem da CVM, mensal e em fração; não é DY de 12 meses. |
| P/VP | Desenvolvido com cobertura variável | `snapshot()`; `p_to_book` aproxima fechamento no mês de referência / VP por cota. Conferir `p_to_book_quote_date`. |
| Identificar segmento | Desenvolvido com cobertura variável | `snapshot()`; `segment` vem da CVM; ausência vira `Sem classificação`. |
| Tabela consolidada de indicadores | Parcial | `fund_profiles.csv` reúne os campos existentes; faltam os indicadores pendentes acima. |

<a id="etapa-4"></a>
## 4. Cálculo das correlações

| Subitem do checklist | Estado | Onde conferir / limite |
|---|---|---|
| Matriz de Pearson | Desenvolvido | `grafo_base.correlation()`; `correlations.csv`. |
| Matriz de Spearman | Pendente | Não calculada na versão 1. |
| Validar matrizes completas e válidas | Parcial | Mínimo de 75 retornos comuns, limites [-1, 1], testes e [overlap.csv](../outputs/experimentos/overlap.csv). Pares insuficientes ficam ausentes; não há garantia de matriz completa nem validação de Spearman. |
| Identificar maiores correlações positivas | Desenvolvido | [pairs.csv](../outputs/experimentos/pairs.csv) é ordenado por `rho` decrescente. |
| Identificar maiores correlações negativas | Parcial | A matriz e `pairs.csv` preservam sinal; ordenar `rho` crescente e filtrar `< 0`. Falta relatório específico; a amostra pode não ter pares negativos. |
| Comparar Pearson e Spearman | Pendente | Depende da implementação de Spearman. |
| Exportar matrizes em CSV | Parcial | Pearson e sobreposição exportados; Spearman pendente. |

<a id="etapa-5"></a>
## 5. Construção dos grafos e pesos

| Subitem do checklist | Estado | Onde conferir / limite |
|---|---|---|
| FIIs como vértices; relações como arestas | Desenvolvido | `similarity()`; inclui isolados e liga pares que atingem o limiar. |
| Peso proporcional à correlação | Desenvolvido na rede limiarizada | `weight = rho` para `rho >= tau`, com `tau > 0`. |
| Peso inversamente proporcional à distância | Pendente | Não existe `weight = 1/d` para Louvain. O atributo `cost = round(1e6/rho)` é custo de caminhos para centralidade, não esse modelo. |
| Tratamento das correlações negativas | Desenvolvido para o modelo atual | Preservadas na matriz; excluídas da rede positiva; admitidas como candidatas a Kruskal por `d = sqrt(2*(1-rho))`. A regra do novo grafo completo ainda deve ser definida. |
| Grafo completo proporcional | Parcial | Kruskal examina todos os pares válidos, mas Louvain usa a rede com limiar. Matriz completa não significa grafo completo usado por Louvain. |
| Grafo completo inverso | Pendente | Definir também a regularização de `d = 0` e pares sem correlação estimável. |
| Validar pesos e quantidade de arestas | Parcial | `topology()`, testes e invariantes de Kruskal cobrem modelos atuais. Falta a validação dos dois grafos completos do checklist. |

O peso composto da consultoria (`0,60*max(rho,0) + 0,20*mesmo_segmento + 0,20*mesma_faixa`) está em `compound_similarity()`. Ele constitui uma comparação adicional; **não corresponde ao modelo inverso do checklist**.

<a id="etapa-6"></a>
## 6. Louvain direto (sem Kruskal)

| Subitem do checklist | Estado | Onde conferir / limite |
|---|---|---|
| Louvain no proporcional | Parcial | `communities()` é chamado na rede positiva limiarizada; falta execução no grafo completo definido no checklist. |
| Registrar comunidades do proporcional | Parcial | `fund_profiles.csv`: comunidade por ticker; `communities.csv`: resumo por comunidade, para a rede atual. |
| Modularidade na rede original proporcional | Parcial | `run.json` → `graph.modularity` é calculada na rede limiarizada que gerou os grupos. Falta a do grafo completo. |
| Louvain, comunidades e modularidade no inverso | Pendente | Modelo inverso ainda não implementado. |
| Tempo de execução | Pendente | Não há medição exportada do tempo de Louvain. |
| Consumo de memória | Pendente | Não há medição exportada de memória. |
| Salvar resultados | Parcial | CSV, GraphML e JSON existentes para a variante atual; falta o protocolo completo. |

<a id="etapa-7"></a>
## 7. Kruskal + Louvain

| Subitem do checklist | Estado | Onde conferir / limite |
|---|---|---|
| Converter correlações em distâncias | Desenvolvido | `algo_mst.kruskal()`: `sqrt(2*(1-rho))`. |
| Construir grafo de distâncias | Desenvolvido como lista de candidatos | Todos os pares válidos são candidatos ordenados internamente; não se exporta um grafo completo de distâncias separado. |
| Executar Kruskal e gerar AGM | Desenvolvido | União de conjuntos evita ciclos; `kruskal_edges.csv` e `kruskal.graphml`. Pode gerar floresta se faltarem conexões. |
| Validar conectividade e N−1 arestas | Desenvolvido | Resumo `kruskal` em `run.json`; execução completa valida aciclicidade e `N-c`. Se `c=1`, são `N-1` arestas. |
| Converter distâncias selecionadas em similaridades para Louvain | Pendente | A árvore guarda `rho` e `distance`; falta preparar o peso de entrada para uma nova detecção nela. |
| Executar Louvain na AGM | Pendente | As cores na figura de Kruskal reutilizam os grupos da rede limiarizada. Não houve nova detecção na árvore. |
| Repetir para proporcional e inverso | Pendente | O Kruskal de Pearson/composto existente não implementa o par de modelos solicitado. |
| Modularidade das partições na rede completa original | Pendente | Não há partição produzida por Louvain na árvore para avaliar. |
| Tempos de Kruskal, Louvain e total | Pendente | Sem medição por etapa. |
| Memória e exportação dos resultados do protocolo | Parcial | Árvore e resumo são exportados; memória e protocolo Kruskal + Louvain pendentes. |

<a id="etapa-8"></a>
## 8. Comparação dos experimentos

| Experimento do PDF | Estado | Diferença em relação à versão 1 |
|---|---|---|
| E1: proporcional + Louvain direto | Parcial | Pearson + Louvain existem, com limiar; falta o grafo completo. |
| E2: inverso + Louvain direto | Pendente | Falta modelo inverso. |
| E3: proporcional + Kruskal + Louvain | Pendente | Kruskal existe, mas falta detectar comunidades na árvore. |
| E4: inverso + Kruskal + Louvain | Pendente | Faltam modelo inverso e detecção na árvore. |

| Critério do checklist | Estado | Evidência / próximo passo |
|---|---|---|
| Número de comunidades e modularidade | Parcial | `comparacao_modelos/comparacao.csv` compara Pearson/composto limiarizados; falta tabela E1–E4. |
| Silhouette com distância adequada | Pendente | Definir tratamento das lacunas, diagonal e casos de partição inválida para Silhouette. |
| Tempo médio e desvio-padrão | Pendente | Definir repetições e registrar os tempos antes de comparar. |
| Memória | Pendente | Definir métrica e registrar a medição nas quatro condições. |
| Estabilidade das comunidades | Parcial | `sensitivity.csv`, `temporal_members.csv` e `run.json` → `temporal` comparam limiares/resoluções e janelas; falta estabilidade E1–E4. |
| Melhor qualidade, melhor desempenho e equilíbrio qualidade/custo | Pendente | A comparação atual não sustenta essa conclusão para os quatro experimentos. |

<a id="etapa-9"></a>
## 9. Mapas e visualizações

| Subitem do checklist | Estado | Onde conferir / limite |
|---|---|---|
| Mapa de calor Pearson | Desenvolvido | [matriz_correlacao.png](../outputs/experimentos/matriz_correlacao.png). |
| Mapa de calor Spearman | Pendente | Depende da matriz de Spearman. |
| Grafo completo de correlação | Parcial | As figuras mostram redes limiarizadas; a visualização pode reduzir arestas exibidas. Os CSVs preservam as arestas calculadas. |
| Filtros por intensidade | Desenvolvido via execução | `main.py --limiar` ou CLI `--tau`; não é um filtro interativo na figura. |
| Visualização da AGM | Desenvolvido | [estrutura_kruskal.png](../outputs/experimentos/estrutura_kruskal.png). |
| Grafo Louvain com cores por comunidade | Desenvolvido | [rede_louvain.png](../outputs/experimentos/rede_louvain.png). |
| Identificar segmentos nos grafos | Parcial | Segmentos constam nos GraphML e tabelas; falta identificação explícita dos segmentos nas figuras PNG. |
| Consultar correlações de cada fundo | Desenvolvido | CLI `inspect`, sobre `pairs.csv` e `fund_profiles.csv`, com diretório de saída explícito no README. |
| Comparar visualmente Louvain direto e Kruskal + Louvain | Pendente | As duas figuras existem, mas usam a mesma partição; isso não compara os dois métodos de detecção. |

<a id="etapa-10"></a>
## 10. Análise e documentação acadêmica

| Subitem do checklist | Estado | Onde conferir / limite |
|---|---|---|
| Correlações entre segmentos e fundos de segmentos diferentes semelhantes | Desenvolvido como análise exploratória | `pairs.csv`, `segment_communities.csv` e `comparacao_modelos/caso_entre_segmentos.csv`; interpretação em [resultados de referência](resultados_referencia.md). |
| Diferenças Pearson/Spearman | Pendente | Spearman não implementado. |
| Impacto dos dois modelos de pesos | Parcial | Há análise Pearson/composto; falta proporcional/inverso. |
| Interpretar comunidades | Desenvolvido para a rede atual | Resultados de referência discutem mistura de segmentos, modularidade baixa e instabilidade. |
| Comparar qualidade e interpretar resultados computacionais | Parcial | Há métricas estruturais; faltam Silhouette, tempo e memória do protocolo E1–E4. |
| Verificar preservação de comunidades por Kruskal | Pendente | Não basta colorir a árvore com os grupos da rede; falta detectar nela e comparar as partições. |
| Responder à pergunta de pesquisa | Parcial | Há evidência para a pergunta exploratória da versão 1; falta concluir o protocolo ampliado do grupo. |
| Tabelas e gráficos | Parcial | Existem para a versão 1; faltam os resultados novos do checklist. |
| Metodologia, experimentos e parâmetros | Desenvolvido para a versão 1 | [metodologia](metodologia.md), `run.json` e [catálogo dos arquivos](mapa_arquivos.md). |
| Resultados e discussão | Parcial | [resultados de referência](resultados_referencia.md) é uma nota técnica; relatório acadêmico final pendente. |
| Conclusões do trabalho | Pendente | Consolidar após o protocolo e a revisão do grupo. |

## Ordem sugerida para o grupo continuar

1. Confirmar a procedência da amostra e completar os indicadores da etapa 3.
2. Implementar Spearman e a comparação com Pearson.
3. Definir os grafos completos proporcional/inverso, incluindo negativos, lacunas e distância zero.
4. Preparar Louvain na árvore e avaliar cada partição na rede original correspondente.
5. Executar E1–E4 com repetições, Silhouette, tempo e memória; depois comparar resultados.
6. Completar figuras, interpretação, relatório, conclusões e [responsabilidades](responsabilidades.md).
