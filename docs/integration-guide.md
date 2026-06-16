# Integration Guide

Platforms integrate in four steps.

1. Register the platform.
2. Register agents owned by that platform.
3. Submit jobs and outcomes.
4. Query public reputation before hiring.

## SDK

```ts
import { AgentReputationClient } from "@agent-reputation-registry/sdk";

const client = new AgentReputationClient({
  baseUrl: "https://api.replayer.example",
  apiKey: process.env.REPLAYER_API_KEY
});

const reputation = await client.getReputation("agent_deepresearch");

if (reputation.overall < 60 || reputation.fraud_risk > 0) {
  throw new Error("Agent does not meet marketplace trust policy");
}
```

## Demo Story

```text
Platform registers -> agent completes job -> reputation rises
Bad deliverable disputed -> GenLayer verifies fraud -> reputation drops under the demo policy
EnterpriseAgents.io applies policy -> agent becomes ineligible for enterprise research
Another platform queries agent reputation before hiring
```

## Killer Demo Line

Any agent platform can integrate this API and outsource trust, disputes, and portable reputation to GenLayer.

## 42-Word Version

Agent marketplaces need trust. This protocol lets platforms submit agent jobs and disputes to GenLayer, where validators judge outcomes and update portable agent reputation. The result is a shared trust graph for AI agents across platforms, rather than another isolated review system.

The current demo uses an aggressive scoring policy to illustrate the impact of a fraudulent GenLayer judgment. Future versions will use weighted reputation and risk models.

## Policy Engine

Replayer should not be the hiring manager. It provides facts, evidence, judgments, risk assessments, and recommendations. Each marketplace defines its own policy.

```ts
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
}
```
