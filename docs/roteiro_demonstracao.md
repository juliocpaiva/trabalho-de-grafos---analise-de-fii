# Roteiro de demonstração — 15 minutos

| Tempo | Ponto para apresentar | Evidência a abrir |
|---|---|---|
| 0–2 min | Explique a lacuna: setores diferentes podem compartilhar movimentos de mercado. | Pergunta em metodologia e um exemplo de `pairs.csv`. |
| 2–4 min | Mostre como sai de preços ajustados, datas e volume para retornos e arestas. | `quality.csv`, `returns`, `correlation` e `similarity` no código. |
| 4–7 min | Contraste Louvain e Kruskal. Mostre o teste de união que impede ciclos; explique por que o custo de caminhos não é o peso bruto de correlação. | `rede_louvain.png`, `estrutura_kruskal.png`, `algo_mst.py`, `algo_louvain.py`. |
| 7–9 min | Compare comunidades com segmentos e entre períodos. | `segmentos_comunidades.png`, `sensibilidade.png`, `estabilidade.png`. |
| 9–12 min | Explique seleção antes do corte, os mesmos seis pesos e mesma janela de avaliação. Mostre a mudança sob filtro de giro. | `carteiras.png`, `portfolio_metrics.csv` nas duas execuções. |
| 12–14 min | Demonstre a consulta de VISC11 pela linha de comando e explique o choque em Shoppings. | `python -m fii_network inspect VISC11 --top 3`, `choques.png`. |
| 14–15 min | Discuta baixa modularidade, poucos eventos e estabilidade limitada. | `docs/resultados_referencia.md`. |

Para a demonstração, abra os arquivos gerados previamente e tenha o cache local. O comando de consulta dispensa internet. A coleta online não precisa fazer parte da apresentação.
