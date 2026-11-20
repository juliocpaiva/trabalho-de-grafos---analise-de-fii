import React, { useMemo, useState } from "react";
import { colorFor, num, segmentShapes, shapePath, short } from "../format.js";

const WIDTH = 1000;
const HEIGHT = 680;

// Grafo SVG com zoom, arraste, tooltip e seleção. Usado pela rede e pela árvore.
// nodes: {ticker, community, segment, x, y}; edges: {a, b, rho, distance?}
export default function Graph({ nodes, edges, selected, onSelect, edgeColor = "#5f7d8c", query = "",
  showDistances = false, maxEdgesPerNode = null, label = "Grafo de FIIs" }) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [drag, setDrag] = useState(null);
  const [hover, setHover] = useState(null);

  const shapes = useMemo(() => segmentShapes(nodes), [nodes]);
  const pos = useMemo(() => {
    if (!nodes.length) return {};
    const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y);
    const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const sx = maxX - minX || 1, sy = maxY - minY || 1;
    return Object.fromEntries(nodes.map((n) => [n.ticker, {
      x: 50 + ((n.x - minX) / sx) * (WIDTH - 100), y: 40 + ((n.y - minY) / sy) * (HEIGHT - 90),
    }]));
  }, [nodes]);

  // Em redes densas, mostra as ligações mais fortes de cada FII; a tabela tem todas.
  const shown = useMemo(() => {
    if (!maxEdgesPerNode || edges.length <= nodes.length * 2) return edges;
    const keep = new Set();
    const byNode = new Map(nodes.map((n) => [n.ticker, []]));
    edges.forEach((e, i) => { byNode.get(e.a)?.push(i); byNode.get(e.b)?.push(i); });
    byNode.forEach((ids) => ids.sort((i, j) => Math.abs(edges[j].rho) - Math.abs(edges[i].rho))
      .slice(0, maxEdgesPerNode).forEach((i) => keep.add(i)));
    return edges.filter((_, i) => keep.has(i));
  }, [edges, nodes, maxEdgesPerNode]);

  const q = query.trim().toLowerCase();
  // A busca apaga o resto; a seleção só destaca o FII e seus vizinhos.
  const focus = useMemo(() => {
    const matched = new Set(nodes.filter((n) => q && short(n.ticker).toLowerCase().includes(q)).map((n) => n.ticker));
    if (!matched.size) return null;
    const near = new Set(matched);
    edges.forEach((e) => { if (matched.has(e.a)) near.add(e.b); if (matched.has(e.b)) near.add(e.a); });
    return near;
  }, [nodes, edges, q, selected]);

  const neighbors = useMemo(() => {
    if (!selected) return null;
    const set = new Set([selected]);
    edges.forEach((e) => { if (e.a === selected) set.add(e.b); if (e.b === selected) set.add(e.a); });
    return set;
  }, [edges, selected]);
  const community = Object.fromEntries(nodes.map((n) => [n.ticker, n.community]));
  const groups = [...new Set(nodes.map((n) => n.community))].sort((a, b) => a - b);

  function changeZoom(next) {
    const z = Math.min(4, Math.max(0.6, next));
    setZoom(z);
    if (z === 1) setPan({ x: 0, y: 0 });
  }
  function onPointerMove(event) {
    if (!drag) return;
    const k = WIDTH / event.currentTarget.getBoundingClientRect().width;
    setPan({ x: drag.pan.x + (event.clientX - drag.x) * k, y: drag.pan.y + (event.clientY - drag.y) * k });
  }

  if (!nodes.length) return <p className="empty">Sem fundos para desenhar.</p>;

  return (
    <div className="graph">
      <div className="graph-tools" aria-label="Controles do grafo">
        <button type="button" onClick={() => changeZoom(zoom * 1.25)} aria-label="Aumentar zoom">+</button>
        <button type="button" onClick={() => changeZoom(zoom / 1.25)} aria-label="Diminuir zoom">−</button>
        <button type="button" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>Ajustar</button>
        <span>{Math.round(zoom * 100)}%</span>
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={label}
        className={zoom > 1 ? "is-zoomed" : ""}
        onWheel={(e) => { e.preventDefault(); changeZoom(zoom * (e.deltaY < 0 ? 1.1 : 0.9)); }}
        onPointerDown={(e) => { if (zoom > 1 && e.target.tagName === "svg") { e.currentTarget.setPointerCapture(e.pointerId); setDrag({ x: e.clientX, y: e.clientY, pan }); } }}
        onPointerMove={onPointerMove} onPointerUp={() => setDrag(null)} onPointerLeave={() => setDrag(null)}>
        <g transform={`translate(${pan.x} ${pan.y}) translate(${WIDTH / 2} ${HEIGHT / 2}) scale(${zoom}) translate(${-WIDTH / 2} ${-HEIGHT / 2})`}>
          {shown.map((e) => {
            const a = pos[e.a], b = pos[e.b];
            if (!a || !b) return null;
            const inside = community[e.a] === community[e.b];
            const dim = focus && !(focus.has(e.a) && focus.has(e.b));
            const strength = Math.min(1, Math.abs(Number(e.rho) || 0));
            const touches = neighbors && (e.a === selected || e.b === selected);
            return (
              <g key={`${e.a}|${e.b}`}>
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={edgeColor}
                  strokeWidth={(0.8 + strength * 2.6) / Math.sqrt(zoom)} strokeDasharray={inside ? "" : "5 4"}
                  opacity={dim ? 0.06 : touches ? 0.95 : neighbors ? 0.16 + strength * 0.3 : 0.22 + strength * 0.5}>
                  <title>{`${short(e.a)} — ${short(e.b)} · ρ ${num(e.rho)}${e.distance !== undefined ? ` · d ${num(e.distance)}` : ""}`}</title>
                </line>
                {(showDistances || touches) && e.distance !== undefined && !dim && (
                  <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2} className="edge-label">{num(e.distance, 2)}</text>
                )}
              </g>
            );
          })}
          {nodes.map((n) => {
            const p = pos[n.ticker];
            const dim = focus && !focus.has(n.ticker);
            const isSelected = selected === n.ticker;
            const near = neighbors?.has(n.ticker) && !isSelected;
            return (
              <g key={n.ticker} transform={`translate(${p.x},${p.y})`} className={`node${dim ? " dim" : ""}${isSelected ? " selected" : ""}${near ? " near" : ""}`}
                onClick={() => onSelect?.(n.ticker)} onMouseEnter={() => setHover(n)} onMouseLeave={() => setHover(null)}
                role="button" tabIndex={0} aria-label={`${short(n.ticker)}, comunidade ${n.community}`}
                onKeyDown={(ev) => { if (ev.key === "Enter") onSelect?.(n.ticker); }}>
                <path d={shapePath(shapes[n.segment || "Sem classificação"], isSelected ? 11 : 8.5)} fill={colorFor(n.community)} />
                <text y={-13} textAnchor="middle">{short(n.ticker)}</text>
              </g>
            );
          })}
        </g>
      </svg>
      {hover && (
        <div className="tooltip" role="status">
          <strong>{short(hover.ticker)}</strong> · comunidade {hover.community}<br />{hover.segment || "Sem classificação"}
        </div>
      )}
      <div className="legend">
        <div><span className="legend-title">Cor = comunidade</span>
          {groups.slice(0, 14).map((g) => <span key={g}><i style={{ background: colorFor(g) }} />{g}</span>)}
          {groups.length > 14 && <span>+{groups.length - 14}</span>}
        </div>
        <div><span className="legend-title">Formato = segmento</span>
          {Object.entries(shapes).map(([seg, shape]) => (
            <span key={seg}><svg width="14" height="14" viewBox="-8 -8 16 16"><path d={shapePath(shape, 5.5)} fill="#5c6f7b" /></svg>{seg}</span>
          ))}
        </div>
        <div className="legend-note">Linha contínua: mesma comunidade · tracejada: comunidades diferentes · espessura: |ρ|
          {shown.length < edges.length && ` · exibindo ${shown.length} de ${edges.length} arestas (as mais fortes de cada FII)`}</div>
      </div>
    </div>
  );
}
