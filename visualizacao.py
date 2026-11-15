"""Figuras acadêmicas estáticas; os CSVs preservam os valores completos."""
import matplotlib

# O modo Agg permite salvar PNGs pelo terminal sem abrir uma janela.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
    palette = plt.get_cmap("RdBu_r" if corr else "Blues").copy()
    palette.set_bad("#ddd")
    img = ax.imshow(table.to_numpy(dtype=float), aspect="auto", cmap=palette,
                    vmin=-1 if corr else 0, vmax=1 if corr else None)
    short = lambda x: str(x).removesuffix(".SA")
    ax.set_xticks(range(len(table.columns)), [short(x) for x in table.columns], rotation=90, fontsize=7)
    ax.set_yticks(range(len(table.index)), [short(x) for x in table.index], fontsize=7)
    ax.set_title(title)
    fig.colorbar(img, ax=ax, shrink=.72)
    save(fig, root, name)


def network(g, membership, root, name, title, seed):
    """Desenha a rede ou floresta com os nós coloridos por comunidade."""
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
