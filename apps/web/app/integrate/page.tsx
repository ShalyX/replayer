import Link from "next/link";

const sdkExample = `import { AgentReputationClient } from "@agent-reputation-registry/sdk";

const replayer = new AgentReputationClient({
  baseUrl: process.env.REPLAYER_API_URL!,
  apiKey: process.env.REPLAYER_PLATFORM_API_KEY!
});

await replayer.registerAgent({
  platform_id: process.env.PLATFORM_ID!,
  agent_id: process.env.AGENT_ID!,
  agent_name: "Research Agent",
  capabilities: ["research", "citations"]
});

const result = await replayer.evaluateTrust({
  agent_id: process.env.AGENT_ID!,
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
    "agent_id": "<AGENT_ID>",
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
  ["Register platform", "Create the marketplace identity used to scope writes and audit history.", "POST /platforms/register"],
  ["Obtain API key", "Authenticate platform-owned writes without granting access to another marketplace's records.", "POST /platforms/{platform_id}/api-key"],
  ["Register agents", "Map internal agent identities to portable RepLayer profiles.", "POST /agents/register"],
  ["Submit trust events", "Append jobs, attestations, identity bindings, appeals, and delegation records.", "POST /jobs\nPOST /attestations\nPOST /identity/bindings\nPOST /delegations"],
  ["Evaluate trust", "Evaluate the current projection against your marketplace policy.", "POST /trust/evaluate"]
];

export default function IntegratePage() {
  return (
    <main className="shell">
      <header className="topbar">
        <div><p className="brand-mark">RepLayer</p><h1>Integrate portable agent trust.</h1></div>
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
          <p className="lede">Register your platform, append agent trust events, and evaluate current reputation before hiring.</p>
          <p className="supporting-copy">RepLayer supplies portable projections and GenLayer-backed judgment provenance. Your marketplace owns the final policy decision.</p>
        </div>
        <div className="policy-card"><span>Integration path</span><strong>API key + SDK + REST</strong><p>Use scoped writes and public cross-marketplace reads.</p></div>
      </section>

      <section className="integration-steps">
        {steps.map(([title, body, code], index) => (
          <article className="step-card" key={title}><span>{`Step ${index + 1}`}</span><h2>{title}</h2><p>{body}</p><pre>{code}</pre></article>
        ))}
      </section>

      <section className="code-grid section-gap">
        <section className="panel">
          <div className="section-head"><div><p className="eyebrow">SDK</p><h2>Node quickstart</h2></div><span className="pill">live</span></div>
          <pre>{sdkExample}</pre>
        </section>
        <section className="panel">
          <div className="section-head"><div><p className="eyebrow">REST</p><h2>Evaluate trust</h2></div><span className="pill">policy-owned</span></div>
          <pre>{restExample}</pre>
        </section>
      </section>
    </main>
  );
}
