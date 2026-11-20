// Chamadas à API FastAPI. Erros viram mensagens legíveis no painel.
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

export const api = {
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
};
