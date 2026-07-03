import Link from "next/link";

const statuses = [
  {
    label: "Hosted API",
    status: "ready",
    detail: "FastAPI service is deployment-ready with Render configuration."
  },
  {
    label: "Platform Accounts",
    status: "ready",
    detail: "Marketplaces can register platform identities."
  },
  {
    label: "API Keys",
    status: "ready",
    detail: "Admin keys create platform keys; platform keys authenticate pilot writes."
  },
  {
    label: "Ownership Enforcement",
    status: "ready",
    detail: "Platform keys can write only to agents and jobs owned by that platform."
  },
  {
    label: "SDK",
    status: "ready",
    detail: "The TypeScript SDK covers platform, agent, job, history, and trust evaluation calls."
  },
  {
    label: "GenLayer Live Mode",
    status: "pilot",
    detail: "Live judgment mode exists, with fallback-safe demo handling for RPC instability."
  },
  {
    label: "Reputation Passport",
    status: "ready",
    detail: "Public agent profiles expose scores, timeline, disputes, and judgment evidence."
  },
  {
    label: "Marketplace Policy Engine",
    status: "ready",
    detail: "Marketplaces submit policy inline to evaluate eligibility without RepLayer owning the decision."
  }
];

export default function PilotPage() {
  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="brand-mark">RepLayer</p>
          <h1>RepLayer Pilot Status</h1>
        </div>
        <nav className="nav">
          <Link className="secondary" href="/">Dashboard</Link>
          <Link className="secondary" href="/integrate">Integrate</Link>
          <Link className="secondary" href="/api">API</Link>
          <a className="secondary" href="https://github.com/ShalyX/replayer" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
      </header>

      <section className="hero-band">
        <div>
          <p className="eyebrow">Pilot adoption readiness</p>
          <p className="lede">
            RepLayer has the core infrastructure a test marketplace needs to evaluate portable agent reputation.
          </p>
          <p className="supporting-copy">
            This dashboard separates what works today from what still needs production hardening before broad release.
          </p>
        </div>
        <div className="pilot-summary">
          <span>Ready items</span>
          <strong>7 / 8</strong>
          <p>GenLayer live mode is pilot-capable while production RPC hardening continues.</p>
        </div>
      </section>

      <section className="status-grid">
        {statuses.map((item) => (
          <article className="status-card" key={item.label}>
            <div className="section-head">
              <h2>{item.label}</h2>
              <span className={`status-badge ${item.status}`}>{item.status}</span>
            </div>
            <p>{item.detail}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
