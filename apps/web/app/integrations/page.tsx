import Link from "next/link";

const snippet = `import { AgentReputationClient } from "@agent-reputation-registry/sdk";

const client = new AgentReputationClient({
  baseUrl: "https://api.replayer.example",
  apiKey: process.env.REPLAYER_API_KEY
});

const reputation = await client.getReputation(agentId);

if (reputation.status === "flagged") {
  rejectAgent();
}`;

export default function IntegrationsPage() {
  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Platform Integration</p>
          <h1>Add Agent Trust in 5 Minutes</h1>
        </div>
        <nav className="nav">
          <Link className="secondary" href="/">Dashboard</Link>
        </nav>
      </header>
      <section className="grid">
        <section className="panel">
          <h2>REST</h2>
          <pre>{`GET /agents/{agent_id}/reputation
GET /agents/{agent_id}/history
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
