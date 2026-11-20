import React from "react";
import { num } from "../format.js";
import Table from "./Table.jsx";

const BEST = { modularidade_grafo_completo: "max", silhouette: "max", estabilidade_sementes: "max",
  estabilidade_temporal_ari: "max", separacao: "max", tempo_medio_ms: "min", memoria_pico_kb: "min" };

function bestValues(rows) {
  return Object.fromEntries(Object.entries(BEST).map(([key, rule]) => {
    const values = rows.map((r) => r[key]).filter((v) => v !== null && v !== undefined);
    return [key, values.length ? (rule === "max" ? Math.max(...values) : Math.min(...values)) : null];
  }));
}

const label = (r) => `${r.experimento} · ${r.correlacao === "pearson" ? "Pearson" : "Spearman"}`;

export default function ProtocolView({ data }) {
  if (!data) return <p className="empty">Carregando experimentos…</p>;
  const rows = data.rows || [];
  const best = bestValues(rows);
  const metric = (key, digits = 3) => ({
    key, num: true, render: (r) => num(r[key], digits),
    className: (r) => (best[key] !== null && r[key] === best[key] ? "best" : ""),
  });
  const winners = (key) => rows.filter((r) => r[key] === true || r[key] === "True").map(label).join(", ") || "—";
  const columns = [
    { key: "experimento", label: "Exp.", render: (r) => <strong>{r.experimento}</strong> },
    { key: "correlacao", label: "Correlação", render: (r) => (r.correlacao === "pearson" ? "Pearson" : "Spearman") },
    { key: "peso", label: "Peso", render: (r) => (r.peso === "proporcional" ? "Proporcional" : "Distância inversa") },
    { key: "deteccao", label: "Detecção" },
    { key: "comunidades", label: "Grupos", num: true },
    { ...metric("modularidade_grafo_completo"), label: "Modularidade" },
    { ...metric("silhouette"), label: "Silhouette" },
    { ...metric("separacao"), label: "Separação ρ" },
    { ...metric("estabilidade_sementes"), label: "Estab. sementes" },
    { ...metric("estabilidade_temporal_ari"), label: "Estab. temporal" },
    { key: "ari_vs_segmento", label: "ARI × segmento", num: true, render: (r) => num(r.ari_vs_segmento) },
    { ...metric("tempo_medio_ms", 1), label: "Tempo (ms)", render: (r) => `${num(r.tempo_medio_ms, 1)} ± ${num(r.tempo_desvio_ms, 1)}` },
    { ...metric("memoria_pico_kb", 0), label: "Memória (KB)" },
    { key: "nota_equilibrio", label: "Nota final", num: true, render: (r) => num(r.nota_equilibrio, 2) },
  ];
  const pres = data.preservation?.pearson || {};
  return (
    <>
      <div className="winners">
        <article><span>Melhor qualidade</span><strong>{winners("melhor_qualidade")}</strong><small>modularidade, Silhouette e estabilidade</small></article>
        <article><span>Menor custo</span><strong>{winners("melhor_custo")}</strong><small>tempo e memória</small></article>
        <article className="main"><span>Melhor equilíbrio</span><strong>{winners("melhor_equilibrio")}</strong><small>70% qualidade · 30% custo</small></article>
      </div>
      <Table columns={columns} rows={rows} rowKey={label} initialSort={{ key: "nota_equilibrio", dir: "desc" }}
        highlight={(r) => r.melhor_equilibrio === true || r.melhor_equilibrio === "True"} />
      <p className="muted small">Verde = melhor valor da coluna. Modularidade sempre medida no grafo completo do modelo, para comparar E1–E4 na mesma régua; em grafo completo ela fica baixa (perto de 0,02) mesmo com grupos bons. {data.repeats ? `${data.repeats} repetições por experimento.` : ""}</p>
      <div className="preservation">
        <h3>A árvore de Kruskal preserva as comunidades? (ARI, 1 = idênticas)</h3>
        <div className="bars">
          {[["Proporcional: E1 × E3", pres.proporcional_E1_vs_E3], ["Distância inversa: E2 × E4", pres.distancia_inversa_E2_vs_E4],
            ["Pesos no grafo completo: E1 × E2", pres.modelos_direto_E1_vs_E2], ["Pesos na árvore: E3 × E4", pres.modelos_arvore_E3_vs_E4]].map(([k, v]) => (
            <div key={k}><span>{k}</span><span className="bar"><i style={{ width: `${Math.max(0, v || 0) * 100}%` }} /></span><strong>{num(v, 2)}</strong></div>
          ))}
        </div>
      </div>
      <div className="figures">
        {(data.images || []).filter((img) => !img.includes("spearman")).map((img) => (
          <figure key={img}><img src={`/api/images/${img}`} alt={img} loading="lazy" /><figcaption>{img.split("/").pop()}</figcaption></figure>
        ))}
        {(data.images || []).filter((img) => img.includes("spearman")).map((img) => (
          <details key={img}><summary>Ver as partições com Spearman</summary>
            <figure><img src={`/api/images/${img}`} alt={img} loading="lazy" /></figure></details>
        ))}
      </div>
    </>
  );
}
