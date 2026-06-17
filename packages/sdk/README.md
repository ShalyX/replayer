# RepLayer SDK

TypeScript client for the RepLayer API.

## Install During Test Phase

Until the package is published to npm, build it from the repo:

```bash
npm install
npm run build --workspace @agent-reputation-registry/sdk
```

## Usage

```ts
import { AgentReputationClient } from "@agent-reputation-registry/sdk";

const client = new AgentReputationClient({
  baseUrl: process.env.REPLAYER_API_URL!,
  apiKey: process.env.REPLAYER_API_KEY!
});

const auth = await client.checkAuth();

const result = await client.evaluateTrust({
  agent_id: "deepresearchbot",
  job_type: "enterprise_research",
  job_value: 50000,
  policy: {
    min_trust_score: 70,
    max_risk_score: 30,
    max_fraud_incidents: 0,
    allow_flagged: false
  }
});
```

