import Link from "next/link";

const snippet = `import { AgentReputationClient } from "@agent-reputation-registry/sdk";

const client = new AgentReputationClient({
  baseUrl: "https://api.replayer.example",
  apiKey: process.env.REPLAYER_API_KEY
});

const result = await client.evaluateTrust({
  agent_id: agentId,
  job_type: "enterprise_research",
  job_value: 50000,
  policy: {
    min_trust_score: 70,
    max_risk_score: 30,
    max_fraud_incidents: 0,
    allow_flagged: false
  }
});

if (!result.policy_result.eligible) {
  routeToManualReview(result.reasons);
}`;

export default function IntegrationsPage() {
  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="brand-mark">RepLayer</p>
          <h1>Add Agent Trust in 5 Minutes</h1>
        </div>
        <nav className="nav">
          <Link className="secondary" href="/">Dashboard</Link>
          <Link className="secondary" href="/marketplace">Marketplace Console</Link>
        </nav>
      </header>
      <section className="grid">
        <section className="panel">
          <h2>REST</h2>
          <pre>{`GET /agents/{agent_id}/reputation
GET /agents/{agent_id}/history
POST /trust/evaluate
POST /jobs/{job_id}/dispute
POST /jobs/{job_id}/evaluate`}</pre>
        </section>
        <section className="panel">
          <h2>SDK Snippet</h2>
          <pre>{snippet}</pre>
        </section>
      </section>
    </main>
  );
}
