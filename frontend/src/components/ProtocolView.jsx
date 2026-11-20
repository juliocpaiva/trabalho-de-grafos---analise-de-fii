import React from "react";
import { methodName, num } from "../format.js";
import Table from "./Table.jsx";

const BEST = { modularidade_grafo_completo: "max", silhouette: "max", estabilidade_sementes: "max",
  estabilidade_temporal_ari: "max", separacao: "max", tempo_medio_ms: "min", memoria_pico_kb: "min" };

function bestValues(rows) {
  return Object.fromEntries(Object.entries(BEST).map(([key, rule]) => {
    const values = rows.map((r) => r[key]).filter((v) => v !== null && v !== undefined);
    return [key, values.length ? (rule === "max" ? Math.max(...values) : Math.min(...values)) : null];
  }));
}

const label = (r) => `${r.experimento} · ${methodName(r.correlacao)}`;
const isTrue = (v) => v === true || v === "True";

export default function ProtocolView({ data }) {
  if (!data) return <p className="empty">Carregando experimentos…</p>;
  const rows = data.rows || [];
  const best = bestValues(rows);
  const metric = (key, digits = 3) => ({
    key, num: true, render: (r) => num(r[key], digits),
    className: (r) => (best[key] !== null && r[key] === best[key] ? "best" : ""),
  });
  const winners = (key) => rows.filter((r) => isTrue(r[key])).map(label).join(", ") || "—";
  const degenerate = rows.filter((r) => isTrue(r.particao_degenerada));
  const columns = [
    { key: "experimento", label: "Exp.", render: (r) => <strong>{r.experimento}</strong> },
    { key: "correlacao", label: "Correlação", render: (r) => methodName(r.correlacao) },
    { key: "peso", label: "Peso", render: (r) => (r.peso === "proporcional" ? "Proporcional" : "Distância inversa") },
    { key: "deteccao", label: "Detecção" },
    { key: "comunidades", label: "Grupos", num: true, render: (r) => (isTrue(r.particao_degenerada)
      ? <span className="degenerate" title="Partição degenerada: não separa os FIIs e não pode vencer">{r.comunidades} ⚠</span> : r.comunidades) },
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
  const variants = Object.keys(data.preservation || {});
  return (
    <>
      <div className="winners">
        <article><span>Melhor qualidade</span><strong>{winners("melhor_qualidade")}</strong><small>modularidade, Silhouette e estabilidade</small></article>
        <article><span>Menor custo</span><strong>{winners("melhor_custo")}</strong><small>tempo e memória</small></article>
        <article className="main"><span>Melhor equilíbrio</span><strong>{winners("melhor_equilibrio")}</strong><small>70% qualidade · 30% custo</small></article>
      </div>
      <Table columns={columns} rows={rows} rowKey={label} initialSort={{ key: "nota_equilibrio", dir: "desc" }}
        highlight={(r) => r.melhor_equilibrio === true || r.melhor_equilibrio === "True"} />
      {degenerate.length > 0 && (
        <div className="notice warn-notice">
          <strong>{degenerate.map(label).join(", ")}</strong> juntaram todos os FIIs num grupo só (⚠). Isso acontece quando o movimento comum do
          mercado domina: no grafo completo quase todo par tem ρ &gt; 0. Essas partições não separam nada e ficam fora do ranking de qualidade.
          Compare com a variante <strong>Pearson sem mercado</strong>, que retira esse movimento comum antes de montar o grafo.
        </div>
      )}
      <p className="muted small">Verde = melhor valor da coluna. Modularidade sempre medida no grafo completo do modelo, para comparar E1–E4 na mesma régua. Com Pearson bruto ela fica perto de zero porque o movimento comum do mercado domina; a variante sem mercado retira esse efeito. {data.repeats ? `${data.repeats} repetições por experimento.` : ""}</p>
      <div className="preservation">
        <h3>A árvore de Kruskal preserva as comunidades? (ARI: 1 = idênticas, 0 = sem relação)</h3>
        <table className="compare">
          <thead><tr><th>Comparação</th>{variants.map((v) => <th key={v} className="num">{methodName(v)}</th>)}</tr></thead>
          <tbody>{[["Proporcional: E1 × E3", "proporcional_E1_vs_E3"], ["Distância inversa: E2 × E4", "distancia_inversa_E2_vs_E4"],
            ["Pesos no grafo completo: E1 × E2", "modelos_direto_E1_vs_E2"], ["Pesos na árvore: E3 × E4", "modelos_arvore_E3_vs_E4"]].map(([text, key]) => (
            <tr key={key}><td>{text}</td>{variants.map((v) => <td key={v} className="num">{num(data.preservation[v]?.[key], 2)}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
      <div className="figures">
        {(data.images || []).filter((img) => !img.includes("particoes_")).map((img) => (
          <figure key={img}><img src={`/api/images/${img}`} alt={img} loading="lazy" /><figcaption>{img.split("/").pop()}</figcaption></figure>
        ))}
        {(data.images || []).filter((img) => img.includes("particoes_")).map((img) => (
          <details key={img}><summary>Ver as partições E1–E4 com {methodName(img.split("particoes_").pop().replace(".png", ""))}</summary>
            <figure><img src={`/api/images/${img}`} alt={img} loading="lazy" /></figure></details>
        ))}
      </div>
    </>
  );
}
