import Link from "next/link";

const quickstart = `npm install @agent-reputation-registry/sdk

import { AgentReputationClient } from "@agent-reputation-registry/sdk";

const replayer = new AgentReputationClient({
  baseUrl: "https://YOUR_API_HOST",
  apiKey: process.env.REPLAYER_PLATFORM_API_KEY!
});

const evaluation = await replayer.evaluateTrust({
  agent_id: "deepresearchbot",
  job_type: "research",
  job_value: 500,
  policy: {
    min_trust_score: 70,
    max_risk_score: 30,
    max_fraud_incidents: 0,
    allow_flagged: false
  }
});`;

const endpoints = [
  ["GET", "/auth/check", "Confirm the active API key is valid."],
  ["POST", "/platforms/register", "Register a marketplace platform with an admin key."],
  ["POST", "/platforms/{platform_id}/api-key", "Create or rotate a platform API key."],
  ["POST", "/agents/register", "Register an agent owned by a platform."],
  ["POST", "/jobs", "Create a job for a registered agent."],
  ["POST", "/jobs/{job_id}/deliverable", "Submit deliverable evidence."],
  ["POST", "/jobs/{job_id}/accept", "Record accepted work and update reputation."],
  ["POST", "/jobs/{job_id}/dispute", "Open a dispute with evidence."],
  ["POST", "/jobs/{job_id}/evaluate", "Evaluate a dispute and record judgment evidence."],
  ["GET", "/agents/{agent_id}/reputation", "Read the current reputation snapshot."],
  ["GET", "/agents/{agent_id}/history", "Read snapshots, judgments, and timeline."],
  ["GET", "/agents/{agent_id}/profile", "Read the public reputation passport data."],
  ["POST", "/trust/evaluate", "Evaluate risk and marketplace policy."]
];

export default function ApiOverviewPage() {
  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="brand-mark">RepLayer</p>
          <h1>Public API Overview</h1>
        </div>
        <nav className="nav">
          <Link className="secondary" href="/">Dashboard</Link>
          <Link className="secondary" href="/integrate">Integrate</Link>
          <Link className="secondary" href="/pilot">Pilot Status</Link>
          <a className="secondary" href="https://github.com/ShalyX/replayer" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
      </header>

      <section className="hero-band">
        <div>
          <p className="eyebrow">Developer surface</p>
          <p className="lede">Use the API directly or install the SDK to add portable trust checks to a marketplace.</p>
          <p className="supporting-copy">
            Authentication uses `x-api-key`. Admin keys create platforms and platform keys submit owned agent/job events.
          </p>
        </div>
        <div className="policy-card">
          <span>Install</span>
          <strong>npm install</strong>
          <pre>npm install @agent-reputation-registry/sdk</pre>
        </div>
      </section>

      <section className="code-grid">
        <section className="panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">Auth model</p>
              <h2>Two key types</h2>
            </div>
          </div>
          <div className="auth-list">
            <article>
              <span>Admin API key</span>
              <p>Registers platforms and rotates platform keys.</p>
            </article>
            <article>
              <span>Platform API key</span>
              <p>Registers owned agents, submits job lifecycle events, reads reputation, and evaluates policy.</p>
            </article>
          </div>
        </section>

        <section className="panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">Quickstart</p>
              <h2>Evaluate an agent</h2>
            </div>
          </div>
          <pre>{quickstart}</pre>
        </section>
      </section>

      <section className="panel section-gap">
        <div className="section-head">
          <div>
            <p className="eyebrow">Endpoints</p>
            <h2>Available pilot API</h2>
          </div>
        </div>
        <div className="endpoint-list">
          {endpoints.map(([method, path, description]) => (
            <article key={`${method}-${path}`}>
              <span>{method}</span>
              <strong>{path}</strong>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
