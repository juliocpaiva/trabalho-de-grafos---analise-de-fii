import React, { useMemo, useState } from "react";

// Tabela com ordenação por coluna. columns: {key, label, render?, num?, sortValue?}
export default function Table({ columns, rows, rowKey, initialSort, highlight, onRowClick, maxHeight = 460 }) {
  const [sort, setSort] = useState(initialSort || { key: null, dir: "desc" });
  const sorted = useMemo(() => {
    if (!sort.key) return rows;
    const col = columns.find((c) => c.key === sort.key);
    const value = (r) => (col?.sortValue ? col.sortValue(r) : r[sort.key]);
    return [...rows].sort((a, b) => {
      const va = value(a), vb = value(b);
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      const cmp = typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb), "pt-BR");
      return sort.dir === "asc" ? cmp : -cmp;
    });
  }, [rows, sort, columns]);

  function toggle(key) {
    setSort((s) => ({ key, dir: s.key === key && s.dir === "desc" ? "asc" : "desc" }));
  }

  if (!rows.length) return <p className="empty">Nenhuma linha para mostrar.</p>;
  return (
    <div className="table-wrap" style={{ maxHeight }}>
      <table>
        <thead><tr>{columns.map((c) => (
          <th key={c.key} className={c.num ? "num" : ""} aria-sort={sort.key === c.key ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}>
            <button type="button" onClick={() => toggle(c.key)}>{c.label}{sort.key === c.key ? (sort.dir === "asc" ? " ↑" : " ↓") : ""}</button>
          </th>))}</tr></thead>
        <tbody>{sorted.map((r, i) => (
          <tr key={rowKey ? rowKey(r) : i} className={`${highlight?.(r) ? "highlight" : ""}${onRowClick ? " clickable" : ""}`}
            onClick={onRowClick ? () => onRowClick(r) : undefined}>
            {columns.map((c) => <td key={c.key} className={`${c.num ? "num" : ""} ${c.className?.(r) || ""}`}>{c.render ? c.render(r) : r[c.key] ?? "—"}</td>)}
          </tr>))}</tbody>
      </table>
    </div>
  );
}
