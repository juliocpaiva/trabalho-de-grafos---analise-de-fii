import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const colors = ["#176b79", "#604899", "#9b4c1a", "#385e36", "#843e60", "#35568a"];

async function getJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error((await response.json()).detail || "Erro na requisição");
  return response.json();
}

function NetworkGraph({ nodes, edges }) {
  const width = 980;
  const columns = 3;
  const clusterWidth = 300;
  const clusterHeight = 150;
  const height = Math.max(520, Math.ceil(new Set(nodes.map((node) => node.community)).size / columns) * clusterHeight + 50);
  const positions = useMemo(() => {
    const result = {};
    const communities = [...new Set(nodes.map((node) => Number(node.community || 1)))].sort((a, b) => a - b);
    communities.forEach((community, communityIndex) => {
      const clusterColumn = communityIndex % columns;
      const clusterRow = Math.floor(communityIndex / columns);
      const members = nodes
        .filter((item) => Number(item.community || 1) === community)
        .sort((a, b) => a.ticker.localeCompare(b.ticker));
      const originX = 32 + clusterColumn * clusterWidth;
      const originY = 48 + clusterRow * clusterHeight;
      members.forEach((node, memberIndex) => {
        result[node.ticker] = {
          x: originX + 28 + (memberIndex % 5) * 50,
          y: originY + 42 + Math.floor(memberIndex / 5) * 48,
        };
      });
    });
    return result;
  }, [nodes]);

  return (
    <svg className="network" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Rede de correlações dos FIIs">
      {edges.slice(0, 280).map((edge, index) => {
        const a = positions[edge.a];
        const b = positions[edge.b];
        if (!a || !b) return null;
        return <line key={index} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="edge" />;
      })}
      {nodes.map((node) => {
        const point = positions[node.ticker];
        if (!point) return null;
        const community = Number(node.community || 1);
        return (
          <g key={node.ticker} className="node" transform={`translate(${point.x},${point.y})`}>
            <circle r="14" fill={colors[(community - 1) % colors.length]} />
            <text textAnchor="middle" dy="28" className="node-label">{node.ticker.replace(".SA", "")}</text>
          </g>
        );
      })}
    </svg>
  );
}

function PortfolioChart({ points }) {
  if (!points.length) return <p className="empty">Carteiras não disponíveis.</p>;
  const width = 760;
  const height = 280;
  const keys = ["A", "B"];
  const values = points.flatMap((point) => keys.map((key) => Number(point[key] || 0))).filter(Number.isFinite);
  const cumulative = {};
  keys.forEach((key) => {
    let total = 1;
    cumulative[key] = points.map((point) => {
      total *= 1 + Number(point[key] || 0);
      return total - 1;
    });
  });
  const all = keys.flatMap((key) => cumulative[key]);
  const min = Math.min(...all);
  const max = Math.max(...all);
  const range = max - min || 1;
  const x = (index) => 38 + (index / Math.max(1, points.length - 1)) * (width - 70);
  const y = (value) => height - 34 - ((value - min) / range) * (height - 70);

  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Retorno acumulado das carteiras">
      {[0, 0.25, 0.5, 0.75, 1].map((fraction) => (
        <line key={fraction} x1="38" x2={width - 32} y1={height - 34 - fraction * (height - 70)} y2={height - 34 - fraction * (height - 70)} className="grid-line" />
      ))}
      {keys.map((key, keyIndex) => (
        <polyline
          key={key}
          fill="none"
          stroke={keyIndex ? "#604899" : "#176b79"}
          strokeWidth="2.5"
          points={cumulative[key].map((value, index) => `${x(index)},${y(value)}`).join(" ")}
        />
      ))}
      {keys.map((key, keyIndex) => (
        <text key={key} x="38" y={18 + keyIndex * 18} fill={keyIndex ? "#604899" : "#176b79"} fontWeight="700">Carteira {key}</text>
      ))}
    </svg>
  );
}

function KruskalTree({ edges }) {
  const width = 980;
  const height = 680;
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(null);
  const [showDistances, setShowDistances] = useState(false);
  const zoomLimits = [0.7, 3];

  function changeZoom(nextZoom) {
    const scale = Math.min(zoomLimits[1], Math.max(zoomLimits[0], nextZoom));
    setZoom(scale);
    if (scale === 1) setPan({ x: 0, y: 0 });
  }

  function resetView() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }

  function handleWheel(event) {
    event.preventDefault();
    changeZoom(zoom * (event.deltaY < 0 ? 1.12 : 0.89));
  }

  function handlePointerDown(event) {
    if (zoom <= 1) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging({ x: event.clientX, y: event.clientY, pan });
  }

  function handlePointerMove(event) {
    if (!dragging) return;
    const scaleFactor = width / event.currentTarget.getBoundingClientRect().width;
    setPan({
      x: dragging.pan.x + (event.clientX - dragging.x) * scaleFactor,
      y: dragging.pan.y + (event.clientY - dragging.y) * scaleFactor,
    });
  }

  function handlePointerUp(event) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragging(null);
  }

  const tickers = [...new Set(edges.flatMap((edge) => [edge.a, edge.b]).filter(Boolean))];
  const adjacency = new Map(tickers.map((ticker) => [ticker, []]));
  edges.forEach((edge) => {
    adjacency.get(edge.a)?.push(edge.b);
    adjacency.get(edge.b)?.push(edge.a);
  });

  const positions = {};
  const assigned = new Set();
  const components = [];

  for (const start of tickers.sort((a, b) => {
    const degreeA = adjacency.get(a)?.length || 0;
    const degreeB = adjacency.get(b)?.length || 0;
    return degreeB - degreeA || a.localeCompare(b);
  })) {
    if (assigned.has(start)) continue;
    const queue = [start];
    const depth = new Map([[start, 0]]);
    assigned.add(start);
    const component = [];

    while (queue.length) {
      const ticker = queue.shift();
      component.push(ticker);
      for (const neighbor of (adjacency.get(ticker) || []).sort()) {
        if (!assigned.has(neighbor)) {
          assigned.add(neighbor);
          depth.set(neighbor, (depth.get(ticker) || 0) + 1);
          queue.push(neighbor);
        }
      }
    }

    components.push({ component, depth });
  }

  const horizontalPadding = 68;
  const verticalPadding = 70;
  const componentHeight = Math.max(1, components.length);
  components.forEach(({ component, depth }, componentIndex) => {
    const levels = new Map();
    component.forEach((ticker) => {
      const level = depth.get(ticker) || 0;
      if (!levels.has(level)) levels.set(level, []);
      levels.get(level).push(ticker);
    });
    const maxLevel = Math.max(...levels.keys());
    const componentTop = verticalPadding + (componentIndex * 180);
    levels.forEach((members, level) => {
      members.sort();
      const availableWidth = width - horizontalPadding * 2;
      members.forEach((ticker, index) => {
        const x = members.length === 1
          ? width / 2
          : horizontalPadding + (availableWidth * index) / (members.length - 1);
        const y = componentTop + ((height - componentTop - 45) * level) / Math.max(1, maxLevel);
        positions[ticker] = { x, y };
      });
    });
  });

  if (!edges.length) return <p className="empty">Árvore não disponível.</p>;

  return (
    <div className="zoomable-graph">
      <div className="zoom-controls" aria-label="Controles de zoom da árvore">
        <button type="button" onClick={() => changeZoom(zoom * 1.2)} title="Aumentar zoom">+</button>
        <button type="button" onClick={() => changeZoom(zoom / 1.2)} title="Diminuir zoom">−</button>
        <button type="button" onClick={resetView} title="Restaurar visão original">Reset</button>
        <button
          type="button"
          className={showDistances ? "active" : ""}
          onClick={() => setShowDistances((value) => !value)}
          title="Mostrar ou ocultar distâncias"
        >
          Distâncias
        </button>
        <span>{Math.round(zoom * 100)}%</span>
      </div>
      <svg
        className={`network kruskal-zoom ${zoom > 1 ? "is-zoomed" : ""}`}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Árvore geradora mínima de Kruskal"
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <g transform={`translate(${pan.x} ${pan.y}) translate(${width / 2} ${height / 2}) scale(${zoom}) translate(${-width / 2} ${-height / 2})`}>
      {edges.map((edge, index) => {
        const a = positions[edge.a];
        const b = positions[edge.b];
        if (!a || !b) return null;
        const x = (a.x + b.x) / 2;
        const y = (a.y + b.y) / 2;
        return (
          <g key={`${edge.a}-${edge.b}-${index}`}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="mst-edge" />
            {showDistances && (
              <>
                <rect x={x - 22} y={y - 10} width="44" height="20" rx="10" className="distance-label" />
                <text x={x} y={y + 3.5} textAnchor="middle" className="distance-text">
                  {Number(edge.distance).toFixed(2)}
                </text>
              </>
            )}
          </g>
        );
      })}
      {tickers.map((ticker) => {
        const point = positions[ticker];
        const edge = edges.find((item) => item.a === ticker || item.b === ticker);
        const community = Number(
          edge?.a === ticker ? edge.a_community : edge?.b_community,
        ) || 1;
        return (
          <g key={ticker} className="node" transform={`translate(${point.x},${point.y})`}>
            <circle r="12" fill={colors[(community - 1) % colors.length]} />
            <text textAnchor="middle" dy="28" className="node-label">{ticker.replace(".SA", "")}</text>
          </g>
        );
      })}
        </g>
      </svg>
    </div>
  );
}

function App() {
  const [summary, setSummary] = useState(null);
  const [funds, setFunds] = useState([]);
  const [network, setNetwork] = useState({ nodes: [], edges: [] });
  const [pairs, setPairs] = useState([]);
  const [tree, setTree] = useState([]);
  const [portfolios, setPortfolios] = useState({ returns: [], metrics: [] });
  const [selected, setSelected] = useState("");
  const [fundDetail, setFundDetail] = useState(null);
  const [tau, setTau] = useState(0.35);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      setError("");
      const results = await Promise.allSettled([
        getJson("/api/summary"),
        getJson("/api/funds"),
        getJson("/api/network"),
        getJson("/api/correlation?limit=120"),
        getJson("/api/tree"),
        getJson("/api/portfolios"),
      ]);
      const [summaryData, fundsData, networkData, pairsData, treeData, portfolioData] = results.map(
        (result) => result.status === "fulfilled" ? result.value : null,
      );
      const failures = results.filter((result) => result.status === "rejected");
      if (failures.length) setError(failures.map((result) => result.reason.message).join("; "));
      if (!summaryData) return;
      setSummary(summaryData);
      setFunds(fundsData);
      setNetwork(networkData);
      setPairs(pairsData);
      setTree(treeData);
      setPortfolios(portfolioData);
      if (!selected && fundsData.length) setSelected(fundsData[0].ticker);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!selected) return;
    getJson(`/api/funds/${encodeURIComponent(selected)}`)
      .then(setFundDetail)
      .catch(() => setFundDetail(null));
  }, [selected]);

  async function runAnalysis() {
    setRunning(true);
    setError("");
    try {
      await getJson(`/api/analyze?tau=${tau}`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">SMAC03 · UNIFEI 2026.2</p>
          <h1>Rede de FIIs</h1>
        </div>
        <div className="run-controls">
          <label>Limiar
            <input type="number" min="0.01" max="1" step="0.05" value={tau} onChange={(event) => setTau(Number(event.target.value))} />
          </label>
          <button onClick={runAnalysis} disabled={running}>{running ? "Executando…" : "Executar análise"}</button>
        </div>
      </header>

      {error && <div className="alert">{error}</div>}

      <section className="kpis">
        <article><span>FIIs elegíveis</span><strong>{summary?.eligible_assets ?? "—"}</strong></article>
        <article><span>Comunidades</span><strong>{summary?.communities ?? "—"}</strong></article>
        <article><span>Arestas da rede</span><strong>{summary?.edges ?? "—"}</strong></article>
        <article><span>Limiar atual</span><strong>{summary?.settings?.tau ?? tau}</strong></article>
      </section>

      <section className="grid">
        <article className="card wide">
          <div className="card-title"><div><p>Visualização</p><h2>Rede por comunidade</h2></div></div>
          <NetworkGraph nodes={network.nodes} edges={network.edges} />
        </article>

        <article className="card">
          <div className="card-title"><div><p>Consulta</p><h2>Perfil do FII</h2></div></div>
          <select value={selected} onChange={(event) => setSelected(event.target.value)}>
            {funds.map((fund) => <option key={fund.ticker} value={fund.ticker}>{fund.ticker.replace(".SA", "")}</option>)}
          </select>
          {fundDetail ? (
            <dl className="profile">
              <dt>Nome</dt><dd>{fundDetail.name || "Não informado"}</dd>
              <dt>Segmento</dt><dd>{fundDetail.segment}</dd>
              <dt>Comunidade</dt><dd>{fundDetail.community}</dd>
              <dt>Grau</dt><dd>{fundDetail.degree}</dd>
              <dt>Intermediação</dt><dd>{Number(fundDetail.betweenness || 0).toFixed(4)}</dd>
            </dl>
          ) : <p className="empty">Selecione um fundo.</p>}
        </article>
      </section>

      <section className="grid kruskal-layout">
        <article className="card wide">
          <div className="card-title"><div><p>Comparação</p><h2>Pares mais correlacionados</h2></div></div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>A</th><th>B</th><th>Pearson</th><th>Sobreposição</th><th>Mesma comunidade</th></tr></thead>
              <tbody>{pairs.slice(0, 20).map((pair, index) => (
                <tr key={`${pair.a}-${pair.b}-${index}`}>
                  <td>{pair.a?.replace(".SA", "")}</td><td>{pair.b?.replace(".SA", "")}</td>
                  <td>{Number(pair.rho).toFixed(3)}</td><td>{pair.overlap}</td>
                  <td>{pair.same_community ? "Sim" : "Não"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </article>

        <article className="card">
          <div className="card-title"><div><p>Estrutura</p><h2>Árvore de Kruskal</h2></div></div>
          <KruskalTree edges={tree} />
        </article>
      </section>

      <section className="card full">
        <div className="card-title"><div><p>Avaliação fora da amostra</p><h2>Retorno acumulado das carteiras</h2></div></div>
        <PortfolioChart points={portfolios.returns} />
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
