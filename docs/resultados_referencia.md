# Execução de referência — cache local de dados reais

Janela observada: 14/11/2024 a 13/11/2026 (496 sessões). A formação termina em 14/11/2025 (250 sessões); a avaliação começa em 17/11/2025 (246 sessões). Yahoo/yfinance retornou preços ajustados para 40 de 42 candidatos; CVBI11 e MALL11 ficaram de fora porque a fonte não retornou histórico válido sob esses identificadores. A aplicação não une séries de tickers diferentes. Dos 40 FIIs, 39 têm segmento, P/VP aproximado, patrimônio e DY mensal no perfil final. Foram desconsiderados 11 preços contestados por comparação com o COTAHIST da B3; nenhuma cotação ajustada foi imputada. Após esse tratamento, nenhum retorno mantido teve magnitude acima de 20%.

| Experimento | Evidência de referência |
|---|---|
| Limiar e resolução | Em resolução 1, a mudança de limiar 0,20 → 0,35 → 0,50 → 0,65 reduz a rede de 673 para 374, 41 e zero arestas. Com 0,35, mudar a resolução de 0,75 para 1,25 altera o número de comunidades de 4 para 13. |
| Comunidades e segmentos | A referência tem 6 comunidades, 3 isolados e modularidade 0,046. Três grupos misturam segmentos; ARI 0,033 e NMI 0,165 entre os 39 fundos com classificação. HSML11 (Shoppings) e PVBI11 (Escritórios) têm correlação de 0,588 apesar de estarem em comunidades distintas. |
| Estrutura e centralidade | VISC11 lidera em intermediação (0,104; 33 vizinhos). Kruskal cobre os 40 vértices em 39 arestas, soma de distâncias 40,3211, igual à solução independente de Prim. |
| Estabilidade temporal | Entre as janelas, ARI 0,008, Jaccard das arestas 0,256 e correlação entre os valores de Pearson de 0,641. O número de arestas passou de 172 para 554 com os 40 fundos comuns. Isso limita a interpretação de grupos como características permanentes dos fundos. |
| Choque | Shoppings apresentou 25 eventos pelo percentil de 5% (corte de −1,134%); 13 coincidem com as datas avaliáveis das duas carteiras. Nesses 13 dias, a média diária foi de −1,54% para A e −1,19% para B. Os valores descrevem co-movimento histórico. |

Na extensão com redes separadas por sinal, o limiar simétrico de 0,35 manteve 374 relações diretas e não encontrou relações inversas. O menor Pearson entre os 780 pares com correlação estimável foi −0,0412; portanto, os 40 fundos aparecem como isolados na rede inversa. Isso é ausência de evidência de relação inversa forte nesta amostra e janela, não evidência de que FIIs nunca se movam em sentidos opostos.

Na comparação sugerida na consultoria, os dois modelos usam **39 FIIs e 741 pares**. ABCP11 ficou fora desse recorte por falta de segmento e patrimônio no registro disponível. Com o mesmo limiar de 0,35, o grafo de Pearson tem 374 arestas (74,9% entre segmentos) e o composto tem 512 (65,6% entre segmentos). Cada modelo formou cinco comunidades, com ARI de 0,036 entre as partições. O peso composto, que recompensa coincidência de segmento e patrimônio, mudou a organização do grafo. A diferença no número de arestas não mede melhora de previsão.

No exemplo escolhido pela maior correlação entre segmentos, HGLG11 consta como Multicategoria e XPLG11 como Logística nos informes usados. O Pearson passou de 0,547 na formação para 0,658 na avaliação. O peso composto da janela inteira foi 0,556, formado por 0,356 de Pearson, zero de segmento e 0,200 por estarem ambos na faixa de R$ 1 bilhão ou mais. A decomposição fica em `outputs/experimentos/comparacao_modelos/caso_entre_segmentos.csv`.

| Carteira / cenário | Sessões comuns | Correlação média | Volatilidade anual | Retorno acumulado | Drawdown máximo |
|---|---:|---:|---:|---:|---:|
| A — base | 237 | 0,484 | 11,80% | −1,26% | −13,62% |
| B — base | 237 | 0,178 | 9,68% | 7,47% | −7,59% |
| A — giro mínimo de R$ 500 mil | 246 | 0,479 | 11,70% | −2,00% | −13,62% |
| B — giro mínimo de R$ 500 mil | 246 | 0,358 | 11,11% | 4,75% | −11,97% |

As estratégias-base usam seis ativos cada: A cobre seis segmentos e duas comunidades de formação; B cobre três segmentos e seis comunidades. No recorte de giro, 35 ativos permanecem no grafo completo. A diferença de correlação entre as carteiras diminui de 0,306 para 0,121. A diferença de volatilidade também diminui; a mudança de ativos elegíveis e de datas avaliáveis impede atribuir tudo ao giro isoladamente. A baixa modularidade e a instabilidade entre janelas recomendam tratar os grupos como evidência exploratória. Não se presume superioridade futura de B.

As métricas são arredondadas nesta página; o cache e os CSVs contêm a precisão exportada. Os testes automatizados usam dados sintéticos somente para propriedades conhecidas e para verificar o fluxo offline.
