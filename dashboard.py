"""Gera um painel HTML interativo e autocontido para os resultados."""

import json
from math import ceil
from pathlib import Path

import networkx as nx


_PAGE = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rede de FIIs — comunidades</title>
<style>
:root{font-family:Inter,"Segoe UI",Arial,sans-serif;color:#142b3b;background:#f3f6f8;font-synthesis:none}
*{box-sizing:border-box}body{margin:0}.top{background:#102b3c;color:white;padding:28px max(24px,calc((100vw - 1440px)/2));}
.topline{display:flex;align-items:center;gap:12px}.mark{width:38px;height:38px;border-radius:12px;background:#31c4aa;color:#102b3c;display:grid;place-items:center;font-weight:900;font-size:20px}
h1{font-size:clamp(23px,3vw,34px);margin:0;letter-spacing:-.7px}.top p{color:#bfd0d9;margin:8px 0 0 50px;font-size:14px}
.wrap{max-width:1440px;margin:0 auto;padding:24px}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:18px}
.toggle{display:flex;background:#e5ecef;padding:4px;border-radius:12px}.toggle button,.button{border:0;border-radius:9px;padding:10px 15px;font-weight:700;cursor:pointer;color:#436071;background:transparent}
.toggle button.active{background:white;color:#102b3c;box-shadow:0 2px 8px #18394a16}.search{margin-left:auto;min-width:230px;border:1px solid #d5e0e5;border-radius:10px;background:white;padding:11px 14px;font:inherit;color:#142b3b}
.button{background:#fff;border:1px solid #d5e0e5}.button:hover,.toggle button:hover{color:#087d70}
.cards{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:14px;margin-bottom:18px}.card,.panel{background:#fff;border:1px solid #e3eaee;border-radius:16px;box-shadow:0 5px 20px #173a4b08}
.card{padding:17px 19px}.label{font-size:12px;color:#6b808d;font-weight:700;text-transform:uppercase;letter-spacing:.7px}.value{font-size:26px;font-weight:750;margin-top:8px;letter-spacing:-.5px}.hint{font-size:12px;color:#7e919d;margin-top:4px}
.layout{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(280px,.8fr);gap:18px}.panel{padding:20px;min-width:0}.panel h2{font-size:17px;margin:0 0 5px}.sub{color:#748793;font-size:13px;margin:0 0 16px}
.graphbox{height:570px;overflow:auto;border:1px solid #edf1f3;border-radius:12px;background:radial-gradient(circle at center,#fbfdfd,#f7f9fa)}
svg{width:100%;height:100%;display:block}.edge{stroke-linecap:round;transition:opacity .15s}.node{cursor:pointer}.node circle{stroke:white;stroke-width:2}.node text{font-size:11px;font-weight:700;fill:#193445;paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}.node.dim{opacity:.13}.node.selected circle{stroke:#142b3b;stroke-width:4}
.legend{display:flex;gap:16px;flex-wrap:wrap;color:#607684;font-size:12px;margin:12px 0 0}.legend span{display:inline-flex;align-items:center;gap:7px}.swatch{width:11px;height:11px;border-radius:50%;display:inline-block}
.community-list{display:grid;gap:9px;max-height:300px;overflow:auto}.community{border:1px solid #e8eef1;border-radius:11px;padding:11px 12px}.community-head{display:flex;justify-content:space-between;font-size:13px;font-weight:750}.community small{color:#718692;font-size:11px}.tickers{color:#435c6a;font-size:12px;line-height:1.55;margin-top:7px;overflow-wrap:anywhere}
.selection{border-radius:11px;background:#f3f7f8;padding:12px;margin-top:14px;color:#536c79;font-size:13px;min-height:44px}
.table-panel{margin-top:18px}.tablewrap{overflow:auto;max-height:430px}table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;color:#718692;font-size:11px;text-transform:uppercase;letter-spacing:.5px;background:#f8fafb;position:sticky;top:0}
th,td{padding:10px 12px;border-bottom:1px solid #edf1f3}td.num{text-align:right;font-variant-numeric:tabular-nums}.pill{font-size:11px;font-weight:750;padding:4px 8px;border-radius:99px}.pill.direct{background:#e2f5f0;color:#087766}.pill.inverse{background:#fff0f2;color:#b14259}
.note{margin:18px 2px 4px;color:#718692;font-size:12px;line-height:1.6}.empty{padding:28px;color:#708692;text-align:center}.footer{padding:24px;text-align:center;color:#8a9ba4;font-size:11px}
@media(max-width:900px){.layout{grid-template-columns:1fr}.graphbox{height:470px}.cards{grid-template-columns:repeat(2,minmax(125px,1fr))}}
@media(max-width:560px){.wrap{padding:14px}.top{padding:22px 16px}.top p{margin-left:0}.toolbar{align-items:stretch}.toggle{width:100%}.toggle button{flex:1}.search{margin:0;width:100%}.cards{gap:9px}.card{padding:13px}.value{font-size:22px}.panel{padding:14px}.graphbox{height:400px}}
</style>
</head>
<body>
<header class="top">
  <div class="topline"><div class="mark">F</div><h1>Relacionamentos entre FIIs</h1></div>
  <p>Comunidades identificadas separadamente por correlação direta e inversa.</p>
</header>
<main class="wrap">
  <div class="toolbar">
    <div class="toggle" role="group" aria-label="Tipo de relação">
      <button id="direct-tab" class="active" aria-pressed="true">Diretas</button>
      <button id="inverse-tab" aria-pressed="false">Inversas</button>
    </div>
    <input id="search" class="search" type="search" placeholder="Buscar ticker (ex.: HGLG11)" aria-label="Buscar ticker">
    <button id="download" class="button">Baixar pares CSV</button>
  </div>
  <section class="cards" aria-label="Resumo">
    <article class="card"><div class="label">FIIs analisados</div><div class="value" id="fund-count">—</div><div class="hint">inclui fundos isolados</div></article>
    <article class="card"><div class="label">Relações fortes</div><div class="value" id="edge-count">—</div><div class="hint" id="threshold-hint">—</div></article>
    <article class="card"><div class="label">Comunidades</div><div class="value" id="community-count">—</div><div class="hint">inclui comunidades unitárias</div></article>
    <article class="card"><div class="label">Modularidade</div><div class="value" id="modularity">—</div><div class="hint">Louvain ponderado</div></article>
  </section>
  <section class="layout">
    <article class="panel">
      <h2 id="graph-title">Rede de relações diretas</h2>
      <p class="sub" id="graph-subtitle">A espessura indica a intensidade. O grafo destaca até duas ligações por FII; a tabela mantém todos os pares.</p>
      <div class="graphbox"><svg id="network" viewBox="0 0 1000 620" role="img" aria-label="Grafo interativo de FIIs"></svg></div>
      <div class="legend"><span><i class="swatch" style="background:#17a68f"></i>Correlação direta</span><span><i class="swatch" style="background:#d85d75"></i>Correlação inversa</span><span>Cor do nó = comunidade</span></div>
      <div id="selection" class="selection">Selecione um fundo no grafo para ver seu perfil.</div>
    </article>
    <aside class="panel">
      <h2>Grupos encontrados</h2><p class="sub">Membros e tamanho de cada comunidade nesta rede.</p>
      <div id="communities" class="community-list"></div>
      <p class="note">Um fundo pode aparecer em grupos diferentes nas abas direta e inversa. Os grupos representam estrutura de rede; nem todo par dentro de uma comunidade necessariamente ultrapassa o limiar.</p>
    </aside>
  </section>
  <section class="panel table-panel">
    <h2 id="pairs-title">Pares mais relacionados</h2>
    <p class="sub">Ordenados pela intensidade absoluta da correlação. O sinal indica se os retornos tendem a variar juntos ou em sentidos opostos.</p>
    <div class="tablewrap"><table><thead><tr><th>FII A</th><th>FII B</th><th>Tipo</th><th class="num">Pearson</th><th class="num">Pregões comuns</th></tr></thead><tbody id="pairs"></tbody></table></div>
    <div id="no-pairs" class="empty" hidden>Nenhum par atingiu o limiar nesta rede.</div>
  </section>
  <p class="note">Pearson mede associação linear histórica, não causalidade nem garantia de comportamento futuro. Os dados e parâmetros desta página foram gerados localmente pelo projeto.</p>
</main>
<div class="footer">Painel local autocontido · não envia dados para serviços externos</div>
<script id="dashboard-data" type="application/json">__DASHBOARD_DATA__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("dashboard-data").textContent);
const svg = document.getElementById("network");
const NS = "http://www.w3.org/2000/svg";
let mode = "direct";
let query = "";
let selected = "";
function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}
function svgEl(tag, attrs, text) {
  const node = document.createElementNS(NS, tag);
  Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
  if (text !== undefined) node.textContent = text;
  return node;
}
function shortTicker(ticker) { return ticker.replace(/\.SA$/i, ""); }
function fmt(value, digits=3) {
  return value === null || value === undefined || !Number.isFinite(Number(value))
    ? "—" : Number(value).toLocaleString("pt-BR", {maximumFractionDigits:digits});
}
function colorFor(group) { return `hsl(${((Number(group)-1)*137.508)%360} 56% 48%)`; }
function current() { return DATA.relations[mode]; }
function coordinates(nodes) {
  const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const dx = maxX - minX || 1, dy = maxY - minY || 1;
  return new Map(nodes.map(n => [n.ticker, {
    x: 65 + ((n.x-minX)/dx)*870,
    y: 48 + ((n.y-minY)/dy)*520
  }]));
}
function renderGraph() {
  const relation = current(), nodes = relation.nodes, edges = relation.edges;
  svg.replaceChildren();
  if (!nodes.length) {
    svg.append(svgEl("text", {x:500,y:310,"text-anchor":"middle",fill:"#718692"}, "Sem fundos disponíveis"));
    return;
  }
  const pos = coordinates(nodes);
  const degrees = new Map(nodes.map(n => [n.ticker, 0]));
  edges.forEach(e => { degrees.set(e.a, degrees.get(e.a)+1); degrees.set(e.b, degrees.get(e.b)+1); });
  const incident = new Map(nodes.map(n => [n.ticker, []]));
  edges.forEach(e => { incident.get(e.a).push(e); incident.get(e.b).push(e); });
  const visible = new Set();
  incident.forEach(items => items.sort((a,b)=>Math.abs(b.rho)-Math.abs(a.rho)).slice(0,2)
    .forEach(e=>visible.add([e.a,e.b].sort().join("\u0000"))));
  const displayEdges=edges.filter(e=>visible.has([e.a,e.b].sort().join("\u0000")));
  const matched = nodes.filter(n => shortTicker(n.ticker).toLowerCase().includes(query));
  const related = new Set(matched.map(n => n.ticker));
  edges.forEach(e => { if (related.has(e.a) || related.has(e.b)) { related.add(e.a); related.add(e.b); } });
  displayEdges.forEach(e => {
    const a=pos.get(e.a), b=pos.get(e.b);
    const line=svgEl("line",{x1:a.x,y1:a.y,x2:b.x,y2:b.y,class:"edge",
      stroke:mode==="direct"?"#17a68f":"#d85d75",
      "stroke-width":(1+Number(e.strength)*3).toFixed(2),
      opacity:(query && !related.has(e.a) && !related.has(e.b)) ? 0.08 : 0.36+Number(e.strength)*.48});
    line.append(svgEl("title",{},`${shortTicker(e.a)} — ${shortTicker(e.b)} · Pearson ${fmt(e.rho,4)}`));
    svg.append(line);
  });
  nodes.forEach(n => {
    const p=pos.get(n.ticker), group=svgEl("g",{class:"node","data-ticker":n.ticker});
    if (query && !related.has(n.ticker)) group.classList.add("dim");
    if (selected===n.ticker) group.classList.add("selected");
    group.append(svgEl("circle",{cx:p.x,cy:p.y,r:9,fill:colorFor(n.community)}));
    group.append(svgEl("text",{x:p.x+12,y:p.y+4},shortTicker(n.ticker)));
    const detail=[n.ticker,`Comunidade ${n.community}`,n.segment?`Segmento: ${n.segment}`:""].filter(Boolean).join(" · ");
    group.append(svgEl("title",{},detail));
    group.addEventListener("click",()=>showSelection(n,edges,degrees.get(n.ticker)));
    svg.append(group);
  });
}
function showSelection(node, edges, degree) {
  selected=node.ticker;
  const peers=edges.filter(e=>e.a===node.ticker||e.b===node.ticker)
    .sort((a,b)=>Math.abs(b.rho)-Math.abs(a.rho)).slice(0,5)
    .map(e=>`${shortTicker(e.a===node.ticker?e.b:e.a)} (${fmt(e.rho)})`);
  const box=document.getElementById("selection");
  const heading=el("strong","",`${shortTicker(node.ticker)} · comunidade ${node.community}`);
  const text=el("div","",`${node.segment||"Segmento não informado"} · ${degree} relação(ões) fortes`);
  box.replaceChildren(heading,text);
  if (peers.length) box.append(el("div","",`Relações mais fortes: ${peers.join(", ")}`));
  renderGraph();
}
function renderCommunities() {
  const relation=current(), groups=new Map();
  relation.nodes.forEach(n=>{if(!groups.has(n.community))groups.set(n.community,[]);groups.get(n.community).push(n);});
  const host=document.getElementById("communities"); host.replaceChildren();
  [...groups.entries()].sort((a,b)=>b[1].length-a[1].length||a[0]-b[0]).forEach(([id,members])=>{
    const card=el("article","community"), head=el("div","community-head");
    const label=el("span","",`Comunidade ${id}`);
    label.style.color=colorFor(id);
    head.append(label,el("small","",`${members.length} FII${members.length===1?"":"s"}`));
    card.append(head,el("div","tickers",members.map(n=>shortTicker(n.ticker)).sort().join(" · ")));
    host.append(card);
  });
}
function renderPairs() {
  const relation=current(), rows=[...relation.edges].sort((a,b)=>Math.abs(b.rho)-Math.abs(a.rho))
    .filter(e=>!query||shortTicker(e.a).toLowerCase().includes(query)||shortTicker(e.b).toLowerCase().includes(query));
  const body=document.getElementById("pairs"); body.replaceChildren();
  rows.forEach(e=>{
    const row=document.createElement("tr");
    row.append(el("td","",shortTicker(e.a)),el("td","",shortTicker(e.b)));
    row.append(el("td",`pill ${mode==="direct"?"direct":"inverse"}`,mode==="direct"?"Direta":"Inversa"));
    const rho=el("td","num",fmt(e.rho,4)), overlap=el("td","num",Number(e.overlap).toLocaleString("pt-BR"));
    row.append(rho,overlap); body.append(row);
  });
  document.getElementById("no-pairs").hidden=rows.length!==0;
}
function render() {
  const relation=current(), tabDirect=document.getElementById("direct-tab");
  tabDirect.classList.toggle("active",mode==="direct");
  tabDirect.setAttribute("aria-pressed",String(mode==="direct"));
  const tabInverse=document.getElementById("inverse-tab");
  tabInverse.classList.toggle("active",mode==="inverse");
  tabInverse.setAttribute("aria-pressed",String(mode==="inverse"));
  const inverse=mode==="inverse", name=inverse?"inversas":"diretas";
  document.getElementById("fund-count").textContent=relation.nodes.length;
  document.getElementById("edge-count").textContent=relation.edges.length;
  document.getElementById("community-count").textContent=new Set(relation.nodes.map(n=>n.community)).size;
  document.getElementById("modularity").textContent=fmt(relation.modularity,3);
  document.getElementById("threshold-hint").textContent=`|ρ| ≥ ${fmt(relation.tau,2)} · ${inverse?"movimentos opostos":"movimentos na mesma direção"}`;
  document.getElementById("graph-title").textContent=`Rede de relações ${name}`;
  document.getElementById("graph-subtitle").textContent=inverse
    ?"Arestas entre FIIs com correlação negativa forte; espessura indica |Pearson|."
    :"Arestas entre FIIs com correlação positiva forte; espessura indica Pearson.";
  document.getElementById("pairs-title").textContent=`Pares com relação ${inverse?"inversa":"direta"}`;
  renderGraph(); renderCommunities(); renderPairs();
}
function clearSelection() {
  selected="";
  document.getElementById("selection").textContent="Selecione um fundo no grafo para ver seu perfil.";
}
document.getElementById("direct-tab").addEventListener("click",()=>{mode="direct";clearSelection();render();});
document.getElementById("inverse-tab").addEventListener("click",()=>{mode="inverse";clearSelection();render();});
document.getElementById("search").addEventListener("input",event=>{query=event.target.value.trim().toLowerCase();renderGraph();renderPairs();});
document.getElementById("download").addEventListener("click",()=>{
  const relation=current(), rows=[["ticker_a","ticker_b","relation","pearson","strength","overlap"]];
  relation.edges.forEach(e=>rows.push([e.a,e.b,mode==="direct"?"direta":"inversa",e.rho,e.strength,e.overlap]));
  const csv=rows.map(row=>row.map(value=>`"${String(value).replaceAll('"','""')}"`).join(",")).join("\r\n");
  const url=URL.createObjectURL(new Blob(["\ufeff"+csv],{type:"text/csv;charset=utf-8"}));
  const link=document.createElement("a");link.href=url;link.download=`pares_${mode==="direct"?"diretos":"inversos"}.csv`;link.click();URL.revokeObjectURL(url);
});
render();
</script>
</body>
</html>
"""


def _community_positions(graph, membership):
    """Organiza os grupos em células e posiciona seus membros localmente."""
    groups = {}
    for ticker in sorted(graph.nodes):
        community = membership.loc[ticker] if hasattr(membership, "loc") else membership[ticker]
        groups.setdefault(int(community), []).append(ticker)
    if not groups:
        return {}

    columns = ceil(len(groups) ** .5)
    rows = ceil(len(groups) / columns)
    cell_width, cell_height = 940 / columns, 540 / rows
    positions = {}
    for index, (community, members) in enumerate(sorted(groups.items())):
        row, column = divmod(index, columns)
        center_x = 30 + (column + .5) * cell_width
        center_y = 40 + (row + .5) * cell_height
        subgraph = graph.subgraph(members)
        if len(members) == 1:
            local = {members[0]: (0.0, 0.0)}
        elif subgraph.number_of_edges():
            local = nx.spring_layout(subgraph, seed=42 + community, weight="weight", iterations=100)
        else:
            local = nx.circular_layout(subgraph)

        x_values = [float(local[node][0]) for node in members]
        y_values = [float(local[node][1]) for node in members]
        min_x, max_x = min(x_values), max(x_values)
        min_y, max_y = min(y_values), max(y_values)
        span_x, span_y = max_x - min_x, max_y - min_y
        radius_x = min(150, cell_width * .36)
        radius_y = min(120, cell_height * .33)
        for ticker in members:
            x, y = float(local[ticker][0]), float(local[ticker][1])
            normalized_x = (x - min_x) / span_x if span_x else .5
            normalized_y = (y - min_y) / span_y if span_y else .5
            positions[ticker] = (
                center_x + (normalized_x - .5) * 2 * radius_x,
                center_y + (normalized_y - .5) * 2 * radius_y,
            )
    return positions


def relation_payload(graph, membership, modularity, segments=None):
    """Converte uma rede assinada em dados simples para o painel HTML."""
    nodes = sorted(graph.nodes)
    positions = _community_positions(graph, membership)

    funds = []
    for ticker in nodes:
        community = membership.loc[ticker] if hasattr(membership, "loc") else membership[ticker]
        segment = segments.get(ticker, "") if segments is not None else ""
        if segment is None:
            segment = ""
        funds.append({
            "ticker": str(ticker),
            "community": int(community),
            "segment": str(segment),
            "x": float(positions[ticker][0]),
            "y": float(positions[ticker][1]),
        })

    edges = [{
        "a": str(a),
        "b": str(b),
        "rho": float(attrs["rho"]),
        "strength": float(attrs["weight"]),
        "overlap": int(attrs.get("overlap", 0)),
    } for a, b, attrs in sorted(graph.edges(data=True))]
    return {
        "tau": float(graph.graph["tau"]),
        "modularity": None if modularity is None else float(modularity),
        "nodes": funds,
        "edges": edges,
    }


def write_dashboard(output, payload):
    """Grava um painel HTML local, sem CDN nem dependências externas."""
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    for char, escaped in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                          ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        encoded = encoded.replace(char, escaped)
    path = root / "dashboard.html"
    path.write_text(_PAGE.replace("__DASHBOARD_DATA__", encoded), encoding="utf-8")
    return path
