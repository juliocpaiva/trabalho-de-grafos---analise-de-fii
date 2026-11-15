# Matriz de rastreabilidade — SMAC03, Cenário 1

Fonte oficial: Diretrizes do Projeto SMAC03 2026.2, versão local (1), pp. 1–3 e 6, conferida em 15/11/2026. As páginas 4–5 dão orientações para a introdução; as pp. 7–10 referem-se aos outros cenários. RF01–RF10 são identificadores do briefing, não numeração do enunciado.

| ID / requisito | Origem | Interpretação técnica | Entrega responsável | Validação prevista | Status em 15/11/2026 |
|---|---|---|---|---|---|
| RF01 Dataset público | p. 6, entrada do protótipo | Séries ajustadas, volume, eventos, segmentos e fundamentos com fonte | `fonte_yfinance.py` | Auditoria por ativo, conferência B3 e coleta real | Verificado: 40 de 42, 11 preços em quarentena |
| RF02 Modelo relacional | pp. 1 e 6, modelagem | Grafo simples com regra de inclusão, pesos e atributos explícitos | `grafo_base.py`, metodologia | Invariantes e visualização | Verificado: 374 arestas positivas |
| RF03 Similaridades | p. 6, relações e dependências | Pearson, classificação e indicadores disponíveis em medidas separadas | `grafo_base.py`, `experimentos.py` | Correlações, pares e sobreposição | Verificado: 780 pares válidos |
| RF04 Grupos de comportamento | p. 6, comportamento inter e intrassegmento; Louvain no briefing | Detecção ponderada; comparar segmentos e comunidades | `algo_louvain.py`, `experimentos.py` | Grafos conhecidos, tabela cruzada e ARI | Verificado: 6 comunidades |
| RF05 Diversificação e risco | p. 6, composição de carteiras | Comparação A/B com elegibilidade comum e janela posterior | `carteiras_choques.py` | Tickers fixos, métricas e validação temporal | Verificado: 237 sessões comuns |
| RF06 Posições estratégicas | p. 6, estrutura do mercado | Grau, força e intermediação com custo positivo | `grafo_base.py` | Caminhos e rankings | Verificado: três métricas exportadas |
| RF07 Mudanças em segmentos | p. 6, impacto potencial | Choque histórico com comparação de co-movimentos | `carteiras_choques.py` | Eventos conhecidos e número de observações | Verificado: 25 eventos de Shoppings |
| RF08 Exploração | pp. 1 e 6, protótipo e perspectivas | CLI sem interface obrigatória; tabelas consultáveis e figuras | `main.py`, `visualizacao.py` | Execução local e exportação | Verificado: CLI, 9 figuras, CSV e GraphML |
| RF09 Validação e limites | pp. 1 e 6, discussão crítica | Sensibilidade, segmentos, estabilidade, carteiras e choques | `experimentos.py`, testes, relatório | Testes e resultados empíricos | Verificado: 13 testes e 5 experimentos; documentação técnica disponível |
| RF10 Reprodutibilidade | pp. 1–2, código e estratégia; especificação ampliada no briefing | Parâmetros, fontes, versões, cache e execução offline | README, manifestos | Reexecução offline | Verificado com o snapshot armazenado |
| Kruskal | Escolha de método permitida na p. 6, proposta técnica e briefing | Árvore ou floresta de distâncias sobre pares válidos, independente da rede limiarizada | `algo_mst.py` | Aciclicidade, cobertura, custo mínimo, `n-c` arestas | Verificado: 39 arestas e custo comparado com Prim |
| Relatório e apresentação | pp. 1–2 | Template oficial, até 9 páginas; slides de cerca de 15 min e protótipo demonstrável | `docs/` | Conferir PDF, limites e roteiro | Roteiro pronto; relatório acadêmico adiado a pedido; slides finais a preparar |
| Papéis e publicação | pp. 2–3 | Cinco integrantes e corresponsabilidade; artefatos em um repositório | `docs/responsabilidades.md`, README | Revisão pelo grupo; publicação autorizada separadamente | Git local e modelo prontos; preenchimento e publicação pendentes |

As diretrizes não prescrevem algoritmo, limiar, quantidade exata de FIIs ou interface. O briefing mais recente define Louvain para detectar comunidades e Kruskal para a estrutura reduzida. A proposta local de 09/11 coloca Kruskal em primeiro plano; as duas prioridades podem ser acomodadas, pois os algoritmos respondem a questões distintas.
