import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import { num, short } from "../format.js";
import Table from "./Table.jsx";

// Pares de FIIs: maiores correlações, filtro entre segmentos e Pearson × Spearman.
export default function PairsView({ onSelect }) {
  const [cross, setCross] = useState(true);
  const [order, setOrder] = useState("rho");
  const [ticker, setTicker] = useState("");
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = setTimeout(() => {
      api.pairs({ limit: 150, cross_segment: cross, order, ticker }).then((r) => { setRows(r); setError(""); })
        .catch((e) => setError(e.message));
    }, 250);
    return () => clearTimeout(t);
  }, [cross, order, ticker]);

  const columns = [
    { key: "a", label: "FII A", render: (r) => <button type="button" className="link" onClick={() => onSelect(r.a)}>{short(r.a)}</button> },
    { key: "a_segment", label: "Segmento A" },
    { key: "b", label: "FII B", render: (r) => <button type="button" className="link" onClick={() => onSelect(r.b)}>{short(r.b)}</button> },
    { key: "b_segment", label: "Segmento B" },
    { key: "rho", label: "Pearson", num: true, render: (r) => num(r.rho) },
    { key: "spearman", label: "Spearman", num: true, render: (r) => num(r.spearman) },
    { key: "diferenca", label: "Dif.", num: true, render: (r) => num(r.diferenca) },
    { key: "overlap", label: "Pregões", num: true },
    { key: "same_community", label: "Mesma comunidade", render: (r) => (String(r.same_community) === "true" || r.same_community === true ? "Sim" : "Não") },
  ];
  return (
    <>
      <div className="filters">
        <label className="toggle-field"><input type="checkbox" checked={cross} onChange={(e) => setCross(e.target.checked)} /> Só segmentos diferentes</label>
        <label className="field inline">Ordenar por
          <select value={order} onChange={(e) => setOrder(e.target.value)}>
            <option value="rho">Maior Pearson</option>
            <option value="negativo">Menor Pearson (relações opostas)</option>
            <option value="diferenca">Maior diferença Pearson × Spearman</option>
          </select>
        </label>
        <input className="search" type="search" placeholder="Filtrar por FII (ex.: HGLG11)" value={ticker} onChange={(e) => setTicker(e.target.value)} />
      </div>
      {error ? <div className="alert">{error}</div> : <Table columns={columns} rows={rows} rowKey={(r) => `${r.a}|${r.b}`} maxHeight={560} />}
      <p className="muted small">
        {cross ? "Pares de segmentos diferentes que andam juntos: é aqui que a diversificação por segmento falha. " : ""}
        Uma diferença grande entre Pearson e Spearman indica relação puxada por poucos dias extremos.
      </p>
    </>
  );
}
