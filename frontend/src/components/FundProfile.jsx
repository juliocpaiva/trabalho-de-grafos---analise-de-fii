import React from "react";
import { brl, colorFor, num, pct, short } from "../format.js";

// Perfil do FII: segmento, comunidade, indicadores e os pares mais correlacionados.
export default function FundProfile({ funds, selected, onSelect, detail }) {
  const ind = detail?.indicadores || {};
  const facts = detail ? [
    ["Segmento (CVM)", detail.segment || "—"],
    ["Comunidade", <span className="chip" style={{ background: colorFor(detail.community) }}>{detail.community}</span>],
    ["Grau na rede", num(detail.degree, 0)],
    ["Intermediação", num(detail.betweenness, 3)],
    ["Retorno anualizado", pct(ind.retorno_anualizado)],
    ["Volatilidade anual", pct(ind.volatilidade_anual ?? detail.volatility)],
    ["Drawdown máximo", pct(ind.drawdown_maximo)],
    ["Beta", num(ind.beta, 2)],
    ["DY mensal", pct(ind.dy_mensal ?? detail.monthly_yield, 2)],
    ["P/VP", num(ind.p_vp ?? detail.p_to_book, 2)],
    ["Patrimônio", brl(ind.patrimonio ?? detail.net_assets)],
    ["Volume médio/dia", brl(ind.volume_financeiro_medio_brl)],
  ] : [];
  return (
    <div className="profile">
      <label className="field">FII
        <select value={selected} onChange={(e) => onSelect(e.target.value)}>
          {funds.map((f) => <option key={f.ticker} value={f.ticker}>{short(f.ticker)} · {f.segment}</option>)}
        </select>
      </label>
      {!detail ? <p className="empty">Selecione um fundo na lista ou clique em um nó do grafo.</p> : (
        <>
          <dl>{facts.map(([k, v]) => <React.Fragment key={k}><dt>{k}</dt><dd>{v}</dd></React.Fragment>)}</dl>
          {detail.protocolo && (
            <p className="muted small">Comunidade em cada experimento: {Object.entries(detail.protocolo).map(([k, v]) => `${k} ${v}`).join(" · ")}</p>
          )}
          <h3>Mais correlacionados</h3>
          <ul className="peers">
            {(detail.pairs || []).map((p) => (
              <li key={p.peer}>
                <button type="button" onClick={() => onSelect(p.peer)}>{short(p.peer)}</button>
                <span className={`tag ${p.same_segment === false || p.same_segment === "False" ? "tag-cross" : ""}`}>{p.peer_segment || "—"}</span>
                <span className="bar"><i style={{ width: `${Math.max(0, Number(p.rho)) * 100}%` }} /></span>
                <strong>{num(p.rho, 2, true)}</strong>
              </li>
            ))}
          </ul>
          <p className="muted small">Em laranja, pares de segmentos diferentes: a diversificação por segmento não protege contra eles.</p>
        </>
      )}
    </div>
  );
}
