import Link from "next/link";

const sdkExample = `import { AgentReputationClient } from "@agent-reputation-registry/sdk";

const replayer = new AgentReputationClient({
  baseUrl: process.env.REPLAYER_API_URL!,
  apiKey: process.env.REPLAYER_PLATFORM_API_KEY!
});

await replayer.registerAgent({
  platform_id: "researchagents_io",
  agent_id: "deepresearchbot",
  agent_name: "DeepResearchBot",
  capabilities: ["research", "citations"]
});

const result = await replayer.evaluateTrust({
  agent_id: "deepresearchbot",
  job_type: "enterprise_research",
  job_value: 50000,
  policy: {
    min_trust_score: 70,
    max_risk_score: 30,
    max_fraud_incidents: 0,
    allow_flagged: false
  }
});`;

const restExample = `curl -X POST https://YOUR_API_HOST/trust/evaluate \\
  -H "content-type: application/json" \\
  -H "x-api-key: $REPLAYER_PLATFORM_API_KEY" \\
  -d '{
    "agent_id": "deepresearchbot",
    "job_type": "enterprise_research",
    "job_value": 50000,
    "policy": {
      "min_trust_score": 70,
      "max_risk_score": 30,
      "max_fraud_incidents": 0,
      "allow_flagged": false
    }
  }'`;

const steps = [
  {
    title: "Register platform",
    body: "Create the marketplace account RepLayer will use to separate ownership, writes, and audit history.",
    code: `POST /platforms/register`
  },
  {
    title: "Obtain API key",
    body: "Use the platform key for owned writes and trust evaluation calls. Platform keys cannot write to another platform's agents.",
    code: `POST /platforms/{platform_id}/api-key`
  },
  {
    title: "Register agents",
    body: "Map your internal agent identity to a RepLayer agent profile with capabilities and optional metadata.",
    code: `POST /agents/register`
  },
  {
    title: "Submit job lifecycle events",
    body: "Send job creation, deliverable submission, accepted work, dispute opening, and dispute evaluation events.",
    code: `POST /jobs
POST /jobs/{job_id}/deliverable
POST /jobs/{job_id}/accept
POST /jobs/{job_id}/dispute`
  },
  {
    title: "Evaluate trust",
    body: "Ask RepLayer for facts, risk, recommendation, timeline, and a result against your own marketplace policy.",
    code: `POST /trust/evaluate`
  }
];

export default function IntegratePage() {
  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="brand-mark">RepLayer</p>
          <h1>Integrate portable agent trust.</h1>
        </div>
        <nav className="nav">
          <Link className="secondary" href="/">Dashboard</Link>
          <Link className="secondary" href="/api">API</Link>
          <Link className="secondary" href="/pilot">Pilot Status</Link>
          <Link className="secondary" href="/marketplace">Marketplace Console</Link>
          <a className="secondary" href="https://github.com/ShalyX/replayer" target="_blank" rel="noreferrer">GitHub</a>
        </nav>
      </header>

      <section className="hero-band">
        <div>
          <p className="eyebrow">Marketplace integration</p>
          <p className="lede">
            Register your platform, send agent work events, and evaluate trust before a marketplace hires an agent.
          </p>
          <p className="supporting-copy">
            RepLayer supplies portable reputation, GenLayer-backed judgment evidence, and policy evaluation. Your marketplace owns the final hiring decision.
          </p>
        </div>
        <div className="policy-card">
          <span>Current pilot path</span>
          <strong>API key + SDK + REST</strong>
          <p>Use platform-scoped writes for your own agents and public trust reads for cross-marketplace evaluation.</p>
        </div>
      </section>

      <section className="integration-steps">
        {steps.map((step, index) => (
          <article className="step-card" key={step.title}>
            <span>{`Step ${index + 1}`}</span>
            <h2>{step.title}</h2>
            <p>{step.body}</p>
            <pre>{step.code}</pre>
          </article>
        ))}
      </section>

      <section className="code-grid section-gap">
        <section className="panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">SDK</p>
              <h2>Node quickstart</h2>
            </div>
            <span className="pill">pilot</span>
          </div>
          <pre>{sdkExample}</pre>
        </section>

        <section className="panel">
          <div className="section-head">
            <div>
              <p className="eyebrow">REST</p>
              <h2>Evaluate trust</h2>
            </div>
            <span className="pill">policy-owned</span>
          </div>
          <pre>{restExample}</pre>
        </section>
      </section>
    </main>
  );
}
