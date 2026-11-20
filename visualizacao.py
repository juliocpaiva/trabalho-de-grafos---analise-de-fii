"""Figuras acadêmicas estáticas; os CSVs preservam os valores completos."""
from collections import defaultdict
from math import ceil, sqrt

import matplotlib

# O modo Agg permite salvar PNGs pelo terminal sem abrir uma janela.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import networkx as nx
import numpy as np


def save(fig, root, name):
    fig.savefig(root / f"{name}.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def heatmap(table, root, name, title, corr=False):
    """Desenha a matriz de Pearson ou a contagem por segmento e comunidade."""
    # A escala de Pearson é fixa de -1 a +1 e o cinza identifica lacunas.
    n = max(table.shape)
    fig, ax = plt.subplots(figsize=(max(6, n * .23), max(3.1, len(table.index) * .23 + 1)))
    palette = plt.get_cmap("RdBu_r" if corr else "Blues").with_extremes(bad="#ddd")
    img = ax.imshow(table.to_numpy(dtype=float), aspect="auto", cmap=palette,
                    vmin=-1 if corr else 0, vmax=1 if corr else None)
    short = lambda x: str(x).removesuffix(".SA")
    ax.set_xticks(range(len(table.columns)), [short(x) for x in table.columns], rotation=90, fontsize=7)
    ax.set_yticks(range(len(table.index)), [short(x) for x in table.index], fontsize=7)
    ax.set_title(title)
    fig.colorbar(img, ax=ax, shrink=.72)
    save(fig, root, name)


def _visible_edges(g):
    """Mantém todas as arestas de redes esparsas e destaca as fortes nas densas."""
    if g.number_of_edges() <= 2 * len(g):
        return list(g.edges)

    # A união das escolhas de cada fundo preserva ao menos um vizinho para
    # todo vértice conectado. Empates usam o ticker para repetir o desenho.
    selected = set()
    for node in g:
        peers = sorted(g[node], key=lambda peer: (-g[node][peer]["weight"], peer))
        selected.update(tuple(sorted((node, peer))) for peer in peers[:2])
    return sorted(selected)


def _similarity_network(g, membership, root, name, title):
    """Posiciona os vértices em blocos com espaço reservado para cada ticker."""
    palette = ("#176b79", "#604899", "#9b4c1a", "#385e36", "#843e60", "#35568a")
    relation_color = "#c34f68" if g.graph.get("relation") == "inversa" else "#176b79"
    groups, isolates = defaultdict(list), []
    for ticker in sorted(g):
        if g.degree(ticker):
            groups[int(membership[ticker])].append(ticker)
        else:
            isolates.append(ticker)

    columns = min(3, max(1, len(groups)))
    width = 5.35
    panels = []
    positions = {}
    y = 0.0
    entries = sorted(groups.items())
    for first in range(0, len(entries), columns):
        row = entries[first:first + columns]
        counts = [min(5, max(4, ceil(sqrt(len(nodes))))) for _, nodes in row]
        height = 1.12 + .86 * max(ceil(len(nodes) / count) for (_, nodes), count in zip(row, counts))
        for col, ((group, nodes), count) in enumerate(zip(row, counts)):
            x = col * width
            color = palette[(group - 1) % len(palette)]
            panels.append((x, y, width - .27, height, f"Comunidade {group}", nodes, color))
            spacing = (width - .27) / count
            for i, ticker in enumerate(nodes):
                positions[ticker] = (x + (i % count + .5) * spacing, y + 1.28 + (i // count) * .86)
        y += height + .36

    if isolates:
        count = columns * 5
        height = 1.12 + .86 * ceil(len(isolates) / count)
        box_width = columns * width - .27
        panels.append((0, y, box_width, height, "Isolados", isolates, "#586779"))
        for i, ticker in enumerate(isolates):
            positions[ticker] = ((i % count + .5) * box_width / count, y + 1.28 + (i // count) * .86)
        y += height + .36

    height_inches = 1.8 + .76 * max(y, 2)
    fig = plt.figure(figsize=(max(8.5, 4.5 * columns), height_inches), facecolor="#f4f7fa")
    header, footer = 1.0, .68
    ax = fig.add_axes([.04, footer / height_inches, .92, 1 - (header + footer) / height_inches])
    ax.set(xlim=(-.15, columns * width), ylim=(max(y, 2), -.14))
    ax.set_axis_off()
    for x, top, box_width, box_height, label, nodes, color in panels:
        ax.add_patch(FancyBboxPatch((x, top), box_width, box_height,
                     boxstyle="round,pad=0.03,rounding_size=0.15", facecolor="white",
                     edgecolor="#d8e2eb", linewidth=1.0, zorder=0))
        ax.text(x + .20, top + .40, label, color=color, fontsize=11, fontweight="bold", va="center")
        ax.text(x + box_width - .20, top + .40, f"{len(nodes)} FIIs", ha="right",
                va="center", color="#4a5b6b", fontsize=9)

    display = _visible_edges(g)
    within = [(a, b) for a, b in display if membership[a] == membership[b]]
    across = [(a, b) for a, b in display if membership[a] != membership[b]]
    # Primeiro as arestas, depois os tickers com fundo opaco. Assim os
    # nomes permanecem legíveis mesmo nas ligações entre comunidades.
    for edges, color, alpha, style in (
        (within, relation_color, .42, "solid"), (across, "#607695", .25, "dashed")
    ):
        if edges:
            nx.draw_networkx_edges(g, positions, edgelist=edges, ax=ax, edge_color=color,
                                   alpha=alpha, style=style, width=.9)
    for _, _, _, _, _, nodes, color in panels:
        for ticker in nodes:
            x, top = positions[ticker]
            ax.text(x, top, ticker.removesuffix(".SA"), va="center", ha="center", zorder=3,
                    fontsize=8.5, fontweight="normal", color="#142737",
                    bbox=dict(boxstyle="round,pad=.37", fc="white", ec=color, lw=1.0))

    fig.text(.04, 1 - .25 / height_inches, title, fontsize=19, fontweight="bold",
             color="#142737", va="top")
    relation = "inversa" if g.graph.get("relation") == "inversa" else "direta"
    threshold = f"   ·   Limiar |ρ| {g.graph['tau']:.2f} · relação {relation}".replace(".", ",")
    fig.text(.04, 1 - .66 / height_inches,
             f"{len(g)} FIIs   ·   {g.number_of_edges()} arestas   ·   "
             f"{membership.nunique()} comunidades{threshold}", fontsize=10.5, color="#455a6b", va="top")
    note = "Traço contínuo dentro da comunidade e tracejado entre comunidades."
    if len(display) < g.number_of_edges():
        note = (f"Exibidas {len(display)} de {g.number_of_edges()} arestas, pela união das duas mais fortes por FII."
                "\nTracejado liga comunidades diferentes. As tabelas contêm todas as arestas e seus pesos.")
    elif not display:
        note = "Nenhum par atingiu o limiar de similaridade."
    fig.text(.04, .29 / height_inches, note, va="center", fontsize=9, color="#455a6b")
    save(fig, root, name)


def network(g, membership, root, name, title, seed):
    """Desenha a rede ou floresta com os nós coloridos por comunidade."""
    if "tau" in g.graph:
        _similarity_network(g, membership, root, name, title)
        return
    # A semente fixa o desenho. Posição na imagem ajuda a leitura, e as
    # distâncias do algoritmo ficam na tabela de arestas.
    fig, ax = plt.subplots(figsize=(11, 8))
    pos = nx.spring_layout(g, seed=seed, weight="weight", k=1.25 / np.sqrt(max(1, len(g))))
    nx.draw_networkx_edges(g, pos, alpha=.35, edge_color="#35586a", ax=ax)
    nx.draw_networkx_nodes(g, pos, node_color=[(int(membership[t]) - 1) % 20 for t in g],
                           cmap=plt.get_cmap("tab20"), vmin=0, vmax=19, node_size=240,
                           edgecolors="#30424b", linewidths=.5, ax=ax)
    nx.draw_networkx_labels(g, pos, {t: t.removesuffix(".SA") for t in g},
                            font_size=6.5, ax=ax)
    ax.margins(.10)
    ax.set_title(title + "\nCores: comunidades Louvain; a cor pode se repetir acima de 20 grupos")
    ax.set_axis_off()
    save(fig, root, name)


def pair_periods(case, root):
    """Mostra o Pearson do mesmo par nas janelas de formação e avaliação."""
    fig, ax = plt.subplots(figsize=(6, 4))
    values = [case["rho_formation"], case["rho_test"]]
    bars = ax.bar(["Formação", "Avaliação"], values, color=["#606b91", "#176b79"])
    ax.axhline(0, color="#333", linewidth=.7)
    ax.bar_label(bars, fmt="%.3f", padding=3)
    a, b = (case[k].removesuffix(".SA") for k in ("a", "b"))
    ax.set(title=f"{a} × {b} em duas janelas", ylabel="Correlação de Pearson",
           ylim=(-1.15, 1.15))
    save(fig, root, "caso_entre_segmentos")


def experiments(root, sensitivity, portfolio, shocks, central, temporal):
    """Gera as figuras de sensibilidade, centralidade, tempo e carteiras."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for res, group in sensitivity.groupby("resolution"):
        group = group.sort_values("tau")
        axes[0].plot(group.tau, group.communities, marker="o", label=f"res. {res:g}")
        axes[1].plot(group.tau, group.modularity.astype(float), marker="o", label=f"res. {res:g}")
    for ax, title in zip(axes, ["Comunidades (inclui isolados)", "Modularidade ponderada"]):
        ax.set(xlabel="Limiar de Pearson", title=title)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    save(fig, root, "sensibilidade")
    fig, ax = plt.subplots(figsize=(8, 4))
    top = central.head(12).sort_values("betweenness")
    ax.barh([x.removesuffix(".SA") for x in top.index], top.betweenness, color="#176b79")
    ax.set(xlabel="Intermediação normalizada", title="Posições estruturais no grafo positivo")
    save(fig, root, "centralidade")
    if temporal.get("status") == "avaliada":
        fig, ax = plt.subplots(figsize=(7, 3.8))
        vals = [temporal["adjusted_rand"], temporal["edge_jaccard"], temporal["pair_rho_pearson"]]
        ax.bar(["ARI das partições", "Jaccard das arestas", "Pearson dos pesos"], vals, color="#176b79")
        ax.axhline(0, color="#333", linewidth=.7)
        ax.set(title="Estabilidade entre formação e avaliação", ylim=(-1, 1.05))
        save(fig, root, "estabilidade")
    # Mantém as datas com retorno para ambas as carteiras antes de
    # multiplicar os fatores diários e traçar o acumulado.
    evaluated = portfolio.dropna()
    if not evaluated.empty:
        fig, ax = plt.subplots(figsize=(9, 4.2))
        ((1 + evaluated).cumprod() - 1).plot(ax=ax)
        ax.set(ylabel="Retorno acumulado (fração)", title="Carteiras A e B fora da amostra")
        ax.grid(alpha=.2)
        save(fig, root, "carteiras")
    if not shocks.empty and "event_mean" in shocks:
        rows = shocks[shocks.group_type.eq("carteira fora da amostra")].dropna(subset=["event_mean"])
        if not rows.empty:
            fig, ax = plt.subplots(figsize=(7, 4))
            rows.set_index("group")[["event_mean", "other_mean"]].mul(100).rename(columns={
                "event_mean": "Dias de choque", "other_mean": "Demais dias"
            }).plot.bar(ax=ax, rot=0)
            ax.set(xlabel="Carteira", ylabel="Retorno diário médio (%)", title="Associação histórica em dias de choque")
            save(fig, root, "choques")


_SEGMENT_MARKERS = "osD^vP*Xph<>"


def protocol_partitions(tree, partitions, segments, root, seed, name="protocolo_particoes"):
    """Quatro painéis (E1–E4) com a mesma posição dos FIIs: só as cores mudam.

    A posição vem da árvore de Kruskal. Cor = comunidade do experimento;
    formato do marcador = segmento da CVM. Assim dá para ver a olho se as
    comunidades seguem ou atravessam os segmentos.
    """
    pos = nx.kamada_kawai_layout(tree, weight=None) if tree.number_of_edges() else nx.circular_layout(tree)
    seg = segments.reindex(list(tree)).fillna("Sem classificação")
    shapes = {s: _SEGMENT_MARKERS[i % len(_SEGMENT_MARKERS)] for i, s in enumerate(sorted(seg.unique()))}
    fig, axes = plt.subplots(2, 2, figsize=(14, 11.5))
    cmap = plt.get_cmap("tab20")
    for ax, column in zip(axes.flat, ["E1", "E2", "E3", "E4"]):
        members = partitions[column]
        nx.draw_networkx_edges(tree, pos, ax=ax, alpha=.35, edge_color="#5a6b78", width=.8)
        for segment, marker in shapes.items():
            nodes = [t for t in tree if seg[t] == segment]
            nx.draw_networkx_nodes(tree, pos, nodelist=nodes, node_shape=marker, ax=ax, node_size=170,
                                   node_color=[cmap((int(members[t]) - 1) % 20) for t in nodes],
                                   edgecolors="#26343d", linewidths=.5)
        nx.draw_networkx_labels(tree, {t: (x, y + .045) for t, (x, y) in pos.items()},
                                {t: t.removesuffix(".SA") for t in tree}, font_size=6, ax=ax)
        ax.set_title(f"{column}: {members.nunique()} comunidades", fontsize=12, fontweight="bold")
        ax.set_axis_off()
    handles = [plt.Line2D([], [], marker=m, linestyle="", color="#55636e", label=s, markersize=8)
               for s, m in shapes.items()]
    fig.legend(handles=handles, loc="lower center", ncol=min(5, len(handles)), fontsize=9,
               title="Formato = segmento (CVM)", frameon=False)
    fig.suptitle("Comunidades em E1–E4 sobre a mesma árvore de Kruskal\n"
                 "E1/E2 = Louvain no grafo completo · E3/E4 = Louvain na árvore · cor = comunidade",
                 fontsize=14)
    fig.subplots_adjust(bottom=.1, top=.9, hspace=.12, wspace=.05)
    save(fig, root, name)


METHOD_LABELS = {"pearson": "Pearson", "spearman": "Spearman", "pearson_sem_mercado": "Pearson sem mercado"}


def protocol_metrics(table, root, name="protocolo_metricas"):
    """Barras lado a lado das métricas de qualidade e tempo médio com desvio."""
    metrics = [("modularidade_grafo_completo", "Modularidade no grafo completo"),
               ("silhouette", "Silhouette (distância d)"),
               ("estabilidade_sementes", "Estabilidade entre sementes (ARI)"),
               ("tempo_medio_ms", "Tempo médio (ms, ± desvio)")]
    methods = list(dict.fromkeys(table.correlacao))
    experiments = list(dict.fromkeys(table.experimento))
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.2))
    width = .8 / max(1, len(methods))
    colors = ("#176b79", "#c47a2c", "#604899")
    x = np.arange(len(experiments))
    for ax, (column, title) in zip(axes, metrics):
        for i, method in enumerate(methods):
            rows = table[table.correlacao.eq(method)].set_index("experimento").reindex(experiments)
            values = pd_to_float(rows[column])
            err = pd_to_float(rows["tempo_desvio_ms"]) if column == "tempo_medio_ms" else None
            ax.bar(x + (i - (len(methods) - 1) / 2) * width, values, width, yerr=err,
                   color=colors[i % len(colors)], label=METHOD_LABELS.get(method, method), capsize=3)
        ax.set_xticks(x, experiments)
        ax.set_title(title, fontsize=11)
        ax.axhline(0, color="#333", linewidth=.6)
        ax.grid(axis="y", alpha=.2)
    axes[0].legend(fontsize=9)
    degenerate = table[table.get("particao_degenerada", False) == True]  # noqa: E712
    note = ("" if degenerate.empty else "\nSem barra de Silhouette = partição degenerada (um grupo só): "
            + ", ".join(f"{r.experimento} {METHOD_LABELS.get(r.correlacao, r.correlacao)}" for r in degenerate.itertuples()))
    fig.suptitle("Protocolo E1–E4: qualidade e custo" + note, fontsize=13, fontweight="bold")
    fig.tight_layout()
    save(fig, root, name)


def pearson_vs_spearman(table, root, name="pearson_vs_spearman"):
    """Dispersão Pearson × Spearman por par; distância da diagonal = divergência."""
    data = table.dropna(subset=["pearson", "spearman"])
    fig, ax = plt.subplots(figsize=(6.2, 6))
    ax.scatter(data.pearson, data.spearman, s=12, alpha=.55, color="#176b79")
    low = float(min(data.pearson.min(), data.spearman.min(), 0)) if len(data) else -1
    ax.plot([low, 1], [low, 1], color="#c34f68", linewidth=1, label="Pearson = Spearman")
    for row in data.head(5).itertuples():
        ax.annotate(f"{row.a.removesuffix('.SA')}–{row.b.removesuffix('.SA')}", (row.pearson, row.spearman),
                    fontsize=7, xytext=(4, -8), textcoords="offset points")
    ax.set(xlabel="Pearson", ylabel="Spearman", title="Pearson × Spearman por par de FIIs")
    ax.legend(fontsize=8)
    ax.grid(alpha=.2)
    save(fig, root, name)


def pd_to_float(series):
    """Converte uma coluna com None para float (NaN), aceita pelo matplotlib."""
    return np.array([np.nan if v is None else float(v) for v in series], dtype=float)
