import React, { useCallback, useEffect, useRef, useState } from "react";
import { STATIC, api } from "./api.js";
import { experimentName, methodName, num, short } from "./format.js";
import FundProfile from "./components/FundProfile.jsx";
import Graph from "./components/Graph.jsx";
import IndicatorsView from "./components/IndicatorsView.jsx";
import PairsView from "./components/PairsView.jsx";
import PortfolioView from "./components/PortfolioView.jsx";
import ProtocolView from "./components/ProtocolView.jsx";

const TABS = [
  ["rede", "Rede"], ["e1e4", "Experimentos E1–E4"], ["arvore", "Árvore de Kruskal"],
  ["pares", "Pares"], ["carteiras", "Carteiras"], ["indicadores", "Indicadores"],
];

function Card({ eyebrow, title, actions, children, className = "" }) {
  return (
    <article className={`card ${className}`}>
      <header className="card-title">
        <div><p>{eyebrow}</p><h2>{title}</h2></div>
        {actions && <div className="card-actions">{actions}</div>}
      </header>
      {children}
    </article>
  );
}

function Segmented({ value, onChange, options, label }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={v} type="button" className={value === v ? "active" : ""} aria-pressed={value === v} onClick={() => onChange(v)}>{text}</button>
      ))}
    </div>
  );
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [funds, setFunds] = useState([]);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState(null);
  const [tab, setTab] = useState("rede");
  const [relation, setRelation] = useState("direct");
  const [network, setNetwork] = useState(null);
  const [treeColor, setTreeColor] = useState("E3");
  const [treeVariant, setTreeVariant] = useState("pearson_sem_mercado");
  const [tree, setTree] = useState(null);
  const [showDistances, setShowDistances] = useState(false);
  const [protocol, setProtocol] = useState(null);
  const [portfolios, setPortfolios] = useState(null);
  const [indicators, setIndicators] = useState(null);
  const [query, setQuery] = useState("");
  const [tau, setTau] = useState(0.35);
  const [repeats, setRepeats] = useState(5);
  const [job, setJob] = useState({ state: "parada" });
  const [error, setError] = useState("");
  const poll = useRef(null);

  const soft = (promise, setter) => promise.then(setter).catch((e) => { setter(null); if (e.status !== 404) setError(e.message); });

  const load = useCallback(async () => {
    setError("");
    try {
      const s = await api.summary();
      setSummary(s);
      if (s.status !== "avaliada") return;
      setTau(s.settings?.tau ?? 0.35);
      const list = await api.funds();
      setFunds(list);
      setSelected((current) => (current && list.some((f) => f.ticker === current) ? current : list[0]?.ticker || ""));
      soft(api.protocol(), setProtocol);
      soft(api.portfolios(), setPortfolios);
      soft(api.indicators(), setIndicators);
    } catch (e) {
      setError(STATIC ? `Não foi possível carregar os dados publicados: ${e.message}.`
        : `Não foi possível falar com a API: ${e.message}. Ela está rodando? (uvicorn backend.main:app)`);
    }
  }, []);

  useEffect(() => { load(); api.status().then(setJob).catch(() => {}); }, [load]);
  useEffect(() => { if (summary?.status === "avaliada") soft(api.network(relation), setNetwork); }, [relation, summary]);
  useEffect(() => { if (summary?.status === "avaliada") soft(api.tree(treeColor, treeVariant), setTree); }, [treeColor, treeVariant, summary]);
  useEffect(() => {
    if (!selected) return;
    api.fund(selected).then(setDetail).catch(() => setDetail(null));
  }, [selected, summary]);

  useEffect(() => {
    if (job.state !== "executando") return undefined;
    poll.current = setInterval(async () => {
      const status = await api.status().catch(() => null);
      if (!status) return;
      setJob(status);
      if (status.state !== "executando") {
        clearInterval(poll.current);
        if (status.state === "concluida") load();
      }
    }, 2000);
    return () => clearInterval(poll.current);
  }, [job.state, load]);

  async function runAnalysis() {
    setError("");
    try { setJob(await api.analyze(tau, repeats)); } catch (e) { setError(e.message); }
  }

  function select(ticker) {
    setSelected(ticker);
    if (tab !== "rede" && tab !== "arvore") setTab("rede");
  }

  const ready = summary?.status === "avaliada";
  const running = job.state === "executando";
  const balance = summary?.winners?.melhor_equilibrio?.[0];

  return (
    <main>
      <header className="topbar">
        <div>
          <p className="eyebrow">SMAC03 · UNIFEI 2026.2 · Cenário 1</p>
          <h1>Rede de FIIs</h1>
          {ready && <p className="subtitle">
            {summary.window?.first && `${new Date(summary.window.first + "T12:00").toLocaleDateString("pt-BR")} a ${new Date(summary.window.last + "T12:00").toLocaleDateString("pt-BR")} · `}
            {summary.eligible_assets} de {summary.candidate_assets} FIIs elegíveis · limiar ρ ≥ {num(summary.settings?.tau, 2)}
            {summary.source === "sintético" && <span className="badge warn">dados sintéticos de teste</span>}
          </p>}
        </div>
        {STATIC ? (
          <div className="published">
            <span className="badge info">Versão publicada</span>
            <p className="subtitle">Resultados pré-calculados{summary?.window?.last ? ` com dados até ${new Date(summary.window.last + "T12:00").toLocaleDateString("pt-BR")}` : ""}.<br />Para rodar outra análise, use o projeto localmente.</p>
          </div>
        ) : (
        <form className="run-controls" onSubmit={(e) => { e.preventDefault(); runAnalysis(); }}>
          <label>Limiar ρ<input type="number" min="0.05" max="0.95" step="0.05" value={tau} onChange={(e) => setTau(Number(e.target.value))} /></label>
          <label>Repetições E1–E4<input type="number" min="2" max="100" step="1" value={repeats} onChange={(e) => setRepeats(Number(e.target.value))} /></label>
          <button type="submit" disabled={running}>{running ? "Executando…" : "Executar análise"}</button>
        </form>
        )}
      </header>

      {running && <div className="notice"><span className="spinner" />{job.message || "Executando a análise"} Pode levar cerca de 1 minuto; o painel atualiza sozinho.</div>}
      {job.state === "erro" && <div className="alert">A análise falhou: {job.message}</div>}
      {error && <div className="alert">{error}</div>}

      {summary && !ready && !error && (
        <section className="card empty-state">
          <h2>Nenhum resultado ainda</h2>
          <p>Clique em <strong>Executar análise</strong> acima ou rode no terminal <code>python main.py --experimentos</code>.</p>
          <p className="muted">Sem dados coletados? Rode antes <code>python coletar.py</code> (precisa de internet).</p>
        </section>
      )}

      {ready && (<>
        <section className="kpis">
          <article><span>FIIs elegíveis</span><strong>{summary.eligible_assets}</strong><small>de {summary.candidate_assets} candidatos</small></article>
          <article><span>Comunidades</span><strong>{summary.communities}</strong><small>Louvain na rede com limiar</small></article>
          <article><span>Arestas da rede</span><strong>{summary.edges}</strong><small>pares com ρ ≥ {num(summary.settings?.tau, 2)}</small></article>
          <article><span>Comunidades × segmentos</span><strong>{num(summary.comparison?.adjusted_rand, 2)}</strong><small>ARI · perto de 0 = não seguem o segmento</small></article>
          <article className="accent"><span>Melhor E1–E4</span><strong>{balance ? experimentName(balance) : "—"}</strong><small>equilíbrio qualidade × custo</small></article>
        </section>

        <nav className="tabs" aria-label="Seções">
          {TABS.map(([id, text]) => <button key={id} type="button" className={tab === id ? "active" : ""} aria-current={tab === id} onClick={() => setTab(id)}>{text}</button>)}
        </nav>

        {tab === "rede" && (
          <section className="grid">
            <Card eyebrow="Visualização" title={relation === "direct" ? "Rede de relações diretas" : "Rede de relações inversas"}
              actions={<>
                <Segmented label="Tipo de relação" value={relation} onChange={setRelation} options={[["direct", "Diretas ρ ≥ τ"], ["inverse", "Inversas ρ ≤ −τ"]]} />
                <input className="search" type="search" placeholder="Buscar FII" value={query} onChange={(e) => setQuery(e.target.value)} />
              </>}>
              {network ? (network.edges.length || relation === "direct"
                ? <Graph nodes={network.nodes} edges={network.edges} selected={selected} onSelect={setSelected} query={query}
                    edgeColor={relation === "direct" ? "#176b79" : "#c34f68"} maxEdgesPerNode={4} label="Rede de correlações dos FIIs" />
                : <p className="empty">Nenhum par com correlação ≤ −{num(network.tau, 2)}. Nesta amostra os FIIs quase nunca andam em sentidos opostos — isso também é um achado.</p>)
                : <p className="empty">Carregando rede…</p>}
              <p className="muted small">Modularidade {num(network?.modularity)} · clique em um FII para ver o perfil ao lado.</p>
            </Card>
            <Card eyebrow="Consulta" title="Perfil do FII">
              <FundProfile funds={funds} selected={selected} onSelect={setSelected} detail={detail} />
            </Card>
          </section>
        )}

        {tab === "e1e4" && (
          <Card eyebrow="Protocolo" title="Experimentos E1–E4: qual peso e qual caminho encontram os melhores grupos?" className="full">
            <ProtocolView data={protocol} />
          </Card>
        )}

        {tab === "arvore" && (
          <section className="grid">
            <Card eyebrow="Estrutura mínima" title="Árvore geradora mínima (Kruskal)"
              actions={<>
                <Segmented label="Cores" value={treeColor} onChange={setTreeColor}
                  options={[["louvain", "Rede τ"], ["E1", "E1"], ["E2", "E2"], ["E3", "E3"], ["E4", "E4"]]} />
                {treeColor !== "louvain" && (
                  <select aria-label="Correlação do protocolo" value={treeVariant} onChange={(e) => setTreeVariant(e.target.value)}>
                    {["pearson", "spearman", "pearson_sem_mercado"].map((v) => <option key={v} value={v}>{methodName(v)}</option>)}
                  </select>)}
                <label className="toggle-field"><input type="checkbox" checked={showDistances} onChange={(e) => setShowDistances(e.target.checked)} /> Distâncias</label>
              </>}>
              {tree ? <Graph nodes={tree.nodes} edges={tree.edges} selected={selected} onSelect={setSelected}
                showDistances={showDistances} edgeColor="#35586a" label="Árvore geradora mínima de Kruskal" />
                : <p className="empty">Carregando árvore…</p>}
              <p className="muted small">
                {tree?.nodes?.length} FIIs ligados por {tree?.edges?.length} arestas, sem ciclos, com a menor soma de distâncias d = √(2(1 − ρ)).
                Cores: {treeColor === "louvain" ? "comunidades da rede com limiar" : `comunidades do ${treeColor} com ${methodName(treeVariant)} (${tree?.communities} grupos)`}.
                Troque entre E1/E2 e E3/E4 para ver o que a árvore preserva.
              </p>
            </Card>
            <Card eyebrow="Consulta" title="Perfil do FII">
              <FundProfile funds={funds} selected={selected} onSelect={setSelected} detail={detail} />
            </Card>
          </section>
        )}

        {tab === "pares" && <Card eyebrow="Comparação" title="Fundos que andam juntos" className="full"><PairsView onSelect={select} /></Card>}
        {tab === "carteiras" && <Card eyebrow="Diversificação aparente × efetiva" title="Carteira por segmento × carteira por comunidade" className="full"><PortfolioView data={portfolios} /></Card>}
        {tab === "indicadores" && <Card eyebrow="Etapa 3" title="Indicadores por FII" className="full"><IndicatorsView rows={indicators} beta={summary.beta_reference} onSelect={select} /></Card>}

        <footer className="footer">
          Correlação mostra o que andou junto no passado, não causa nem garante o futuro.
          {summary.limitations?.length ? ` ${summary.limitations.length} limitações registradas em run.json.` : ""}
          {selected && ` · Selecionado: ${short(selected)}`}
        </footer>
      </>)}
    </main>
  );
}
