# Rede de FIIs — comece aqui

Protótipo SMAC03, Cenário 1 de Grafos, UNIFEI 2026.2. Investiga se correlações entre retornos de FIIs revelam concentrações que a classificação por segmento não mostra.

**Versão 1: implementação parcial em relação ao checklist do grupo.** Navegação revisada em 18/11/2026. Já existem coleta, Pearson, comunidades na rede limiarizada e árvore de Kruskal. Spearman, peso inverso da distância e o protocolo completo E1–E4 ainda estão pendentes.

## O que você procura?

| Quero… | Abra |
|---|---|
| Saber o que está desenvolvido, parcial ou pendente no PDF | [Checklist comentado, etapas 1–10](docs/estado_checklist.md) |
| Entender o que cada arquivo recebe, faz e retorna | [Mapa dos arquivos e das saídas](docs/mapa_arquivos.md) |
| Ver resultados completos nesta máquina | [outputs/experimentos/](outputs/experimentos/) e seu [run.json](outputs/experimentos/run.json) |
| Entender fórmulas, fontes e decisões | [Metodologia](docs/metodologia.md) |
| Ler a interpretação dos resultados da versão 1 | [Resultados de referência](docs/resultados_referencia.md) |
| Conferir as diretrizes registradas no projeto | [Matriz original de requisitos](docs/matriz_requisitos.md) |
| Apresentar ou dividir tarefas | [Roteiro](docs/roteiro_demonstracao.md) · [Responsabilidades](docs/responsabilidades.md) |

## Onde está cada etapa do checklist?

| Etapa | Arquivos principais | Estado |
|---|---|---|
| [1. Seleção dos FIIs](docs/estado_checklist.md#etapa-1) | `config/amostra.csv`, `fonte_yfinance.py` | Parcial: falta procedência oficial da lista e validação cadastral integral |
| [2. Coleta histórica](docs/estado_checklist.md#etapa-2) | `coletar.py`, `fonte_yfinance.py` | Desenvolvido; depende da disponibilidade das fontes |
| [3. Indicadores](docs/estado_checklist.md#etapa-3) | `fonte_yfinance.py`, `carteiras_choques.py` | Parcial: faltam retorno médio e drawdown por FII, beta IFIX e giro médio |
| [4. Correlações](docs/estado_checklist.md#etapa-4) | `grafo_base.py` | Parcial: Pearson pronto; Spearman pendente |
| [5. Grafos e pesos](docs/estado_checklist.md#etapa-5) | `grafo_base.py`, `algo_mst.py` | Parcial: faltam os dois grafos completos do checklist |
| [6. Louvain direto](docs/estado_checklist.md#etapa-6) | `algo_louvain.py` | Parcial: usa rede limiarizada; faltam protocolo completo, tempo e memória |
| [7. Kruskal + Louvain](docs/estado_checklist.md#etapa-7) | `algo_mst.py` | Parcial: Kruskal pronto; Louvain na árvore pendente |
| [8. Comparação E1–E4](docs/estado_checklist.md#etapa-8) | `comparacao_modelos.py`, `experimentos.py` | Parcial: comparação atual é Pearson/composto; E1–E4 não concluídos |
| [9. Visualizações](docs/estado_checklist.md#etapa-9) | `visualizacao.py` | Parcial: figuras de Pearson, rede e árvore disponíveis |
| [10. Análise acadêmica](docs/estado_checklist.md#etapa-10) | `docs/` | Parcial: notas e metodologia prontas; relatório e conclusões finais pendentes |

Cada etapa tem subitens, evidências e limites no checklist comentado. O peso composto da consultoria **não é o modelo inverso da distância** solicitado no PDF. As cores da árvore usam as comunidades da rede; não demonstram Louvain executado na árvore.

## Rodar pelo VS Code

Abra a pasta `D:\fii`. Em **Terminal → Executar Tarefa…**, escolha:

| Tarefa | Resultado |
|---|---|
| `FIIs: 1 - Análise rápida (offline)` | 5 CSVs e 2 gráficos em `outputs/simples/` |
| `FIIs: 2 - Análise completa da versão 1 (offline)` | Tabelas, grafos, figuras, carteiras e comparação Pearson/composto em `outputs/experimentos/` |
| `FIIs: 3 - Consultar um FII nos resultados completos` | Pede ticker e lê perfil/pares em `outputs/experimentos/`; execute a tarefa 2 antes se necessário |
| `FIIs: 4 - Verificar testes` | Suíte existente com dados sintéticos |
| `FIIs: 5 - Coletar dados (requer internet)` | Baixa dados para `data/coleta_api/`; dispensável para analisar cache existente |

O menu **Executar e Depurar (F5)** oferece as duas análises. Os atalhos usam a `.venv` e a raiz do projeto. As tarefas offline usam explicitamente `data/cache/`, o snapshot local de referência. Caso não exista, rode a coleta e use `data/coleta_api/` no comando ou ajuste o atalho.

### Pelo terminal

Na raiz do projeto, com o ambiente instalado:

```powershell
# Visão rápida usando o snapshot local
.\.venv\Scripts\python.exe main.py --cache data/cache

# Todos os resultados implementados na versão 1
.\.venv\Scripts\python.exe main.py --experimentos --cache data/cache

# Consultar os resultados completos sem recalcular
.\.venv\Scripts\python.exe -m fii_network inspect VISC11 --top 5 --output outputs/experimentos
```

Sem `--cache`, `main.py` prefere `data/coleta_api/` quando há manifesto; caso contrário usa `data/cache/`. O simples gera `correlacoes.csv`; o completo gera `correlations.csv`. O [catálogo de saídas](docs/mapa_arquivos.md) explica cada arquivo.

Para uma instalação nova, use Python 3.11 ou superior:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe coletar.py
.\.venv\Scripts\python.exe main.py --experimentos
```

Caches e resultados estão no `.gitignore` e não acompanham um clone. Os links para saídas só funcionam após geração local. Rodar no mesmo destino pode substituir arquivos; preserve outras configurações em pastas diferentes.

### Ajustar parâmetros ou preservar outra execução

```powershell
.\.venv\Scripts\python.exe main.py --cache data/cache --limiar 0.45 --saida outputs/limiar_045
.\.venv\Scripts\python.exe -m fii_network analyze --cache data/cache --output outputs/liquidez_revisao --min-turnover-brl 500000 --shock-segment Shoppings --quarantine config/quarentena_precos.csv
.\.venv\Scripts\python.exe -m fii_network analyze --help
```

`main.py` aplica a quarentena configurada no projeto; na CLI completa, informe `--quarantine` explicitamente. `--experimentos` significa a análise completa **da versão 1**, não a conclusão de E1–E4.

## Organização das pastas

```text
fii/
  README.md             ← entrada para o grupo
  docs/                 ← checklist, mapa dos arquivos, metodologia e resultados
  config/               ← amostra e auditoria/quarentena de preços
  data/                 ← dados coletados e snapshot local, ignorados pelo Git
  outputs/              ← resultados gerados, ignorados pelo Git
    simples/            ← revisão rápida
    experimentos/       ← revisão completa recomendada
    principal/          ← execução anterior da CLI
    liquidez/           ← referência com filtro financeiro
  tests/                ← testes existentes
  .vscode/              ← tarefas e configurações de execução
  *.py                  ← entradas e módulos, detalhados no mapa dos arquivos
```

Os nomes dos módulos foram preservados. Consulte o [mapa dos arquivos](docs/mapa_arquivos.md) para distinguir programas de entrada e módulos auxiliares.

## Fontes e documentação técnica

Preços e eventos: Yahoo Finance via yfinance. Segmentos e fundamentos: informes mensais da CVM. Evidências de preços contestados: `config/auditoria_b3.csv`; intervalos aplicados: `config/quarentena_precos.csv`.

O [guia técnico anterior](docs/guia_tecnico_v1.md) preserva os detalhes da primeira versão, incluindo formatos de dados complementares. Para o estado atual em relação ao pedido do grupo, use o [checklist comentado](docs/estado_checklist.md).
