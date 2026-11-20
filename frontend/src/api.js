// Chamadas à API FastAPI. Erros viram mensagens legíveis no painel.
//
// Com VITE_STATIC=1 (versão publicada no GitHub Pages) não há servidor:
// o painel lê os arquivos JSON gerados por exportar_site.py em data/.
export const STATIC = import.meta.env.VITE_STATIC === "1";
const BASE = import.meta.env.BASE_URL || "/";

export async function getJson(url, options) {
  const response = await fetch(url, options);
  let body = null;
  try { body = await response.json(); } catch { body = null; }
  if (!response.ok) {
    const error = new Error(body?.detail || `Erro ${response.status} em ${url}`);
    error.status = response.status;
    throw error;
  }
  return body;
}

const data = (name) => getJson(`${BASE}data/${name}`);

let pairsCache = null;
async function staticPairs({ limit = 150, cross_segment = false, order = "rho", ticker = "" }) {
  pairsCache = pairsCache || (await data("pairs.json"));
  let rows = pairsCache;
  if (String(cross_segment) === "true") rows = rows.filter((r) => r.same_segment === false || r.same_segment === "False");
  const t = String(ticker).trim().toUpperCase().replace(/\.SA$/, "");
  if (t) rows = rows.filter((r) => r.a.replace(/\.SA$/, "") === t || r.b.replace(/\.SA$/, "") === t);
  rows = [...rows];
  if (order === "negativo") rows.sort((x, y) => x.rho - y.rho);
  else if (order === "diferenca") rows.sort((x, y) => Math.abs(y.diferenca ?? 0) - Math.abs(x.diferenca ?? 0));
  else rows.sort((x, y) => y.rho - x.rho);
  return rows.slice(0, Number(limit));
}

const live = {
  summary: () => getJson("/api/summary"),
  funds: () => getJson("/api/funds"),
  fund: (ticker) => getJson(`/api/funds/${encodeURIComponent(ticker)}`),
  network: (relation) => getJson(`/api/network?relation=${relation}`),
  tree: (color, variant) => getJson(`/api/tree?color=${color}&variant=${variant}`),
  pairs: (params) => getJson(`/api/pairs?${new URLSearchParams(params)}`),
  protocol: () => getJson("/api/protocol"),
  portfolios: () => getJson("/api/portfolios"),
  indicators: () => getJson("/api/indicators"),
  status: () => getJson("/api/analyze/status"),
  analyze: (tau, repeats) => getJson(`/api/analyze?tau=${tau}&repeats=${repeats}`, { method: "POST" }),
  image: (path) => `/api/images/${path}`,
};

const published = {
  summary: () => data("summary.json"),
  funds: () => data("funds.json"),
  fund: (ticker) => data(`fund/${ticker}.json`),
  network: (relation) => data(`network-${relation}.json`),
  tree: (color, variant) => data(color === "louvain" ? "tree-louvain.json" : `tree-${color}-${variant}.json`),
  pairs: staticPairs,
  protocol: () => data("protocol.json"),
  portfolios: () => data("portfolios.json"),
  indicators: () => data("indicators.json"),
  status: async () => ({ state: "parada" }),
  analyze: async () => { throw new Error("Na versão publicada a análise não roda: os resultados já vêm calculados."); },
  image: (path) => `${BASE}data/images/${path}`,
};

export const api = STATIC ? published : live;
