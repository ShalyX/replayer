import Link from "next/link";
import { api } from "../../lib/api";

export const dynamic = "force-dynamic";

type Health = {
  ok: boolean;
  genlayer_mode: string;
  source_of_truth: string;
  contract_address: string;
  counts: { platforms: number; agents: number; jobs: number };
};

type IndexerHealth = {
  status: string;
  contract_address: string;
  last_processed_block: number;
  last_processed_event_id: string | null;
  last_sync_at: string | null;
  lag: number;
};

export default async function PilotPage() {
  const [runtimeResult, indexerResult] = await Promise.allSettled([
    api<Health>("/health"),
    api<IndexerHealth>("/health/indexer"),
  ]);
  const runtime = runtimeResult.status === "fulfilled" ? runtimeResult.value : null;
  const indexer = indexerResult.status === "fulfilled" ? indexerResult.value : null;
  const healthy = Boolean(runtime?.ok && runtime.genlayer_mode === "live" && indexer?.status === "healthy" && indexer.lag === 0);

  const statuses = [
    {
      label: "API runtime",
      status: runtime?.ok ? "ready" : "unavailable",
      detail: runtime ? `${runtime.counts.platforms} platforms, ${runtime.counts.agents} agents, and ${runtime.counts.jobs} jobs indexed.` : "The API health endpoint did not respond."
    },
    {
      label: "GenLayer source of truth",
      status: runtime?.genlayer_mode === "live" ? "ready" : "unavailable",
      detail: runtime ? `${runtime.source_of_truth} at ${runtime.contract_address}.` : "No live contract status is available."
    },
    {
      label: "Ledger indexer",
      status: indexer?.status === "healthy" ? "ready" : "unavailable",
      detail: indexer ? `Block ${indexer.last_processed_block}, lag ${indexer.lag}, last sync ${indexer.last_sync_at ?? "not yet synced"}.` : "The indexer health endpoint did not respond."
    },
    {
      label: "Projection freshness",
      status: indexer?.status === "healthy" && indexer.lag === 0 ? "ready" : "attention",
      detail: indexer?.lag === 0 ? "Indexed ledger state is current with the configured contract reader." : `Indexer lag is ${indexer?.lag ?? "unknown"}.`
    }
  ];

  return (
    <main className="shell">
      <header className="topbar">
        <div><p className="brand-mark">RepLayer</p><h1>Runtime readiness</h1></div>
        <nav className="nav">
          <Link className="secondary" href="/">Dashboard</Link>
          <Link className="secondary" href="/integrate">Integrate</Link>
          <Link className="secondary" href="/api">API</Link>
          <a className="secondary" href="https://github.com/ShalyX/replayer" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
      </header>

      <section className="hero-band">
        <div>
          <p className="eyebrow">Live system state</p>
          <p className="lede">Readiness is derived from the deployed API and GenLayer indexer, not a release checklist.</p>
          <p className="supporting-copy">Contract mode, indexed counts, synchronization state, and lag are refreshed for each request.</p>
        </div>
        <div className="pilot-summary">
          <span>Current status</span>
          <strong>{healthy ? "Operational" : "Attention required"}</strong>
          <p>{healthy ? "Live contract mode is active and the indexer reports no lag." : "One or more runtime checks are unavailable or behind."}</p>
        </div>
      </section>

      <section className="status-grid">
        {statuses.map((item) => (
          <article className="status-card" key={item.label}>
            <div className="section-head"><h2>{item.label}</h2><span className={`status-badge ${item.status}`}>{item.status}</span></div>
            <p>{item.detail}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
