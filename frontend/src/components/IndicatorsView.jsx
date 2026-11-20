import React from "react";
import { brl, num, pct, short } from "../format.js";
import Table from "./Table.jsx";

export default function IndicatorsView({ rows, beta, onSelect }) {
  if (!rows) return <p className="empty">Carregando indicadores…</p>;
  const columns = [
    { key: "ticker", label: "FII", render: (r) => <button type="button" className="link" onClick={() => onSelect(r.ticker)}>{short(r.ticker)}</button> },
    { key: "segmento", label: "Segmento" },
    { key: "retorno_anualizado", label: "Retorno a.a.", num: true, render: (r) => pct(r.retorno_anualizado) },
    { key: "volatilidade_anual", label: "Volatilidade", num: true, render: (r) => pct(r.volatilidade_anual) },
    { key: "drawdown_maximo", label: "Drawdown", num: true, render: (r) => pct(r.drawdown_maximo) },
    { key: "beta", label: "Beta", num: true, render: (r) => num(r.beta, 2) },
    { key: "dy_mensal", label: "DY mensal", num: true, render: (r) => pct(r.dy_mensal, 2) },
    { key: "p_vp", label: "P/VP", num: true, render: (r) => num(r.p_vp, 2) },
    { key: "volume_financeiro_medio_brl", label: "Volume/dia", num: true, render: (r) => brl(r.volume_financeiro_medio_brl) },
    { key: "patrimonio", label: "Patrimônio", num: true, render: (r) => brl(r.patrimonio) },
  ];
  return (
    <>
      <Table columns={columns} rows={rows} rowKey={(r) => r.ticker} initialSort={{ key: "retorno_anualizado", dir: "desc" }} maxHeight={620} />
      <p className="muted small">Clique no cabeçalho para ordenar. Beta calculado contra: {beta || "—"}. Retorno e volatilidade anualizados com 252 pregões.</p>
    </>
  );
}
