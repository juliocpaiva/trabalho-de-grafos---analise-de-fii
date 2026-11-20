// Formatação em pt-BR e cores das comunidades.
export const short = (ticker) => String(ticker ?? "").replace(/\.SA$/i, "");

const valid = (v) => v !== null && v !== undefined && v !== "" && Number.isFinite(Number(v));

// Arredonda antes de formatar para não exibir "-0".
const clean = (v, digits) => Math.round(Number(v) * 10 ** digits) / 10 ** digits + 0;

export function num(value, digits = 3, fixed = false) {
  return valid(value) ? clean(value, digits).toLocaleString("pt-BR", { maximumFractionDigits: digits, minimumFractionDigits: fixed ? digits : 0 }) : "—";
}

export function pct(value, digits = 1) {
  return valid(value) ? clean(value, digits + 2).toLocaleString("pt-BR", { style: "percent", maximumFractionDigits: digits, minimumFractionDigits: digits }) : "—";
}

export const experimentName = (text) => String(text ?? "").replace(/ (pearson|spearman)$/i, (_, m) => ` · ${m[0].toUpperCase()}${m.slice(1)}`);

// Marcas "redondas" para eixos (ex.: -6%, -4%, …, 2%).
export function niceTicks(min, max, count = 5) {
  const span = max - min || 1;
  const raw = span / count, mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
  const first = Math.floor(min / step), last = Math.ceil(max / step);
  return Array.from({ length: last - first + 1 }, (_, i) => (first + i) * step + 0);
}

export function brl(value) {
  if (!valid(value)) return "—";
  const v = Number(value);
  if (Math.abs(v) >= 1e9) return `R$ ${num(v / 1e9, 2)} bi`;
  if (Math.abs(v) >= 1e6) return `R$ ${num(v / 1e6, 1)} mi`;
  if (Math.abs(v) >= 1e3) return `R$ ${num(v / 1e3, 0)} mil`;
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

// Ângulo áureo: cores bem separadas para qualquer número de comunidades.
export function colorFor(group) {
  const g = Number(group) || 0;
  return `hsl(${((g - 1) * 137.508 + 190) % 360} 52% 44%)`;
}

export const SEGMENT_SHAPES = ["circle", "square", "diamond", "triangle", "triangle-down", "cross"];

export function shapePath(shape, r) {
  switch (shape) {
    case "square": return `M${-r},${-r}h${2 * r}v${2 * r}h${-2 * r}z`;
    case "diamond": return `M0,${-r * 1.3}L${r * 1.3},0L0,${r * 1.3}L${-r * 1.3},0z`;
    case "triangle": return `M0,${-r * 1.3}L${r * 1.2},${r}L${-r * 1.2},${r}z`;
    case "triangle-down": return `M0,${r * 1.3}L${r * 1.2},${-r}L${-r * 1.2},${-r}z`;
    case "cross": { const a = r * 0.45; return `M${-a},${-r}h${2 * a}v${r - a}h${r - a}v${2 * a}h${a - r}v${r - a}h${-2 * a}v${a - r}h${a - r}v${-2 * a}h${r - a}z`; }
    default: return `M${r},0A${r},${r} 0 1,1 ${-r},0A${r},${r} 0 1,1 ${r},0z`;
  }
}

export function segmentShapes(nodes) {
  const segments = [...new Set(nodes.map((n) => n.segment || "Sem classificação"))].sort();
  return Object.fromEntries(segments.map((s, i) => [s, SEGMENT_SHAPES[i % SEGMENT_SHAPES.length]]));
}
