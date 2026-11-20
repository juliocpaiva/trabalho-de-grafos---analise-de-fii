import React, { useMemo, useState } from "react";
import { niceTicks, num, pct, short } from "../format.js";

const SERIES = [{ key: "A", name: "A · diversifica por segmento", color: "#c47a2c" },
  { key: "B", name: "B · diversifica por comunidade", color: "#176b79" }];

function Chart({ points }) {
  const [hover, setHover] = useState(null);
  const W = 900, H = 320, L = 58, R = 120, T = 18, B = 36;
  const data = useMemo(() => {
    const acc = { A: 1, B: 1 };
    return points.map((p) => {
      SERIES.forEach(({ key }) => { acc[key] *= 1 + Number(p[key]); });
      return { date: p.date, A: acc.A - 1, B: acc.B - 1 };
    });
  }, [points]);
  if (!data.length) return <p className="empty">Sem retornos fora da amostra.</p>;
  const values = data.flatMap((d) => [d.A, d.B, 0]);
  const ticks = niceTicks(Math.min(...values), Math.max(...values));
  const min = ticks[0], max = ticks[ticks.length - 1], span = max - min || 1;
  const x = (i) => L + (i / Math.max(1, data.length - 1)) * (W - L - R);
  const y = (v) => T + (1 - (v - min) / span) * (H - T - B);
  const dateTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * (data.length - 1)));
  const last = data[data.length - 1];
  return (
    <div className="chart-box">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Retorno acumulado das carteiras A e B"
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          setHover(Math.max(0, Math.min(data.length - 1, Math.round(((px - L) / (W - L - R)) * (data.length - 1)))));
        }} onMouseLeave={() => setHover(null)}>
        {ticks.map((t) => (<g key={t}><line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="grid-line" />
          <text x={L - 8} y={y(t) + 4} textAnchor="end" className="axis">{pct(t, 0)}</text></g>))}
        <line x1={L} x2={W - R} y1={y(0)} y2={y(0)} className="zero-line" />
        {dateTicks.map((i) => <text key={i} x={x(i)} y={H - 10} textAnchor="middle" className="axis">
          {new Date(data[i].date + "T12:00:00").toLocaleDateString("pt-BR", { month: "short", year: "2-digit" })}</text>)}
        {SERIES.map((s) => (
          <g key={s.key}>
            <polyline fill="none" stroke={s.color} strokeWidth="2.4" points={data.map((d, i) => `${x(i)},${y(d[s.key])}`).join(" ")} />
            <text x={W - R + 8} y={y(last[s.key]) + 4} fill={s.color} className="end-label">{s.key} {pct(last[s.key])}</text>
          </g>
        ))}
        {hover !== null && (<g>
          <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} className="cursor-line" />
          {SERIES.map((s) => <circle key={s.key} cx={x(hover)} cy={y(data[hover][s.key])} r="4" fill={s.color} />)}
        </g>)}
      </svg>
      <div className="chart-legend">
        {SERIES.map((s) => <span key={s.key}><i style={{ background: s.color }} />{s.name}</span>)}
        {hover !== null && <span className="muted">{new Date(data[hover].date + "T12:00:00").toLocaleDateString("pt-BR")}: A {pct(data[hover].A)} · B {pct(data[hover].B)}</span>}
      </div>
    </div>
  );
}

export default function PortfolioView({ data }) {
  if (!data) return <p className="empty">Carregando carteiras…</p>;
  const m = Object.fromEntries((data.metrics || []).map((r) => [r.portfolio, r]));
  const rows = [
    ["Correlação média entre os ativos", "mean_pair_correlation", (v) => num(v, 3), "min"],
    ["Volatilidade anual", "annual_volatility", (v) => pct(v), "min"],
    ["Retorno acumulado", "total_return", (v) => pct(v), "max"],
    ["Drawdown máximo", "max_drawdown", (v) => pct(v), "max"],
    ["Segmentos diferentes", "segments", (v) => num(v, 0), null],
    ["Comunidades diferentes", "formation_communities", (v) => num(v, 0), null],
    ["Pregões avaliados", "days", (v) => num(v, 0), null],
  ];
  const better = (key, rule) => {
    if (!rule || !m.A || !m.B) return null;
    const a = m.A[key], b = m.B[key];
    if (a === null || b === null || a === b) return null;
    return (rule === "min" ? a < b : a > b) ? "A" : "B";
  };
  return (
    <>
      <Chart points={data.returns || []} />
      <div className="two-col">
        <table className="compare">
          <thead><tr><th>Métrica (fora da amostra)</th><th className="num">Carteira A</th><th className="num">Carteira B</th></tr></thead>
          <tbody>{rows.map(([labelText, key, fmt, rule]) => {
            const win = better(key, rule);
            return (<tr key={key}><td>{labelText}</td>
              <td className={`num ${win === "A" ? "best" : ""}`}>{fmt(m.A?.[key])}</td>
              <td className={`num ${win === "B" ? "best" : ""}`}>{fmt(m.B?.[key])}</td></tr>);
          })}</tbody>
        </table>
        <div className="allocation">
          {["A", "B"].map((p) => (
            <div key={p}><h3>Carteira {p}</h3>
              <ul>{(data.allocation || []).filter((r) => r.portfolio === p).map((r) => (
                <li key={r.ticker}><strong>{short(r.ticker)}</strong> <span className="muted">{r.segment} · comunidade {r.formation_community}</span></li>
              ))}</ul></div>
          ))}
        </div>
      </div>
      <p className="muted small">As duas carteiras são montadas com dados até o corte (formação) e avaliadas depois, com pesos iguais e sem custos. Verde = melhor das duas. Se B, escolhida por comunidade, tiver correlação, volatilidade ou drawdown menores que A, escolhida por segmento, a diversificação por segmento era só aparente.</p>
    </>
  );
}
