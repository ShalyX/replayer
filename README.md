# RepLayer

Portable reputation for AI agents, verified by GenLayer.

RepLayer lets agent marketplaces share trust. When an agent is caught delivering fraudulent work, GenLayer verifies the fraud judgment and every integrated platform can see it before hiring that agent again.

![Before/after trust collapse](docs/assets/before-after-trust-collapse.svg)

## Demo Animation

![Reset and Run Demo flow](docs/assets/reset-run-demo.svg)

## Live Demo Flow

```text
1. ResearchAgents.io lists DeepResearchBot.
2. DeepResearchBot completes a good sourced research job.
3. DeepResearchBot submits fabricated citations on a second job.
4. The buyer opens a dispute.
5. GenLayer verifies the fraud judgment: FRAUDULENT.
6. DeepResearchBot's trust score collapses from 77 to 0 because the demo treats verified fraud as severe.
7. Another marketplace checks the public profile before hiring.
```

> Current demo uses an aggressive scoring policy to illustrate the impact of a fraudulent GenLayer judgment. Future versions will use weighted reputation and risk models.

## Screenshots

### Before/After Trust Collapse

![Before and after trust collapse](docs/assets/before-after-trust-collapse.svg)

### Onchain Judgment Card

![Onchain GenLayer judgment card](docs/assets/onchain-judgment-card.svg)

### Agent Comparison

![Agent comparison](docs/assets/agent-comparison.svg)

### SDK Snippet

![SDK snippet](docs/assets/sdk-snippet.svg)

## Why GenLayer?

Agent marketplaces need more than local reviews. They need portable, inspectable judgments that other platforms can trust.

GenLayer is the right layer for this because the dispute outcome is not a simple numeric transaction. Validators evaluate context: the task, the deliverable, the dispute evidence, and whether the agent fabricated work. When fraud is verified, the result becomes a verifiable judgment that downstream platforms can query before hiring the same agent.

That turns agent reputation from `trust me bro` into:

```text
Verdict: FRAUDULENT
Recorded on GenLayer
Tx: 0x...
View on Explorer
```

## Apps

- `apps/api`: FastAPI backend, Postgres schema, mock scoring, GenLayer adapter.
- `apps/web`: Next.js dashboard, public profile, integration page.
- `packages/sdk`: TypeScript client for marketplaces.
- `contracts`: GenLayer Intelligent Contract.
- `infra`: Postgres docker-compose.

## Environment

Start from the included example:

```bash
cp .env.example .env
```

Key settings:

```bash
DATABASE_URL=postgresql+psycopg://replayer:replayer@localhost:5432/replayer
API_KEY=dev-key
GENLAYER_MODE=mock
GENLAYER_CONTRACT_ADDRESS=0x59a8924E6E7D3A460e2154a304fCC2BEfEc3c8Dd
GENLAYER_EXPLORER_BASE_URL=https://explorer-studio.genlayer.com/tx
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

Use `GENLAYER_MODE=live` when you want disputes to call the deployed contract.

## Run Locally

```bash
npm install
docker compose -f infra/docker-compose.yml up -d
```

In one terminal:

```bash
cd apps/api
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
npm run dev:web
```

Open:

```text
http://localhost:3000
```

## Smoke Test

Run the deterministic dispute demo:

```bash
npm run smoke:dispute
```

Expected result:

```text
Good job accepted -> reputation rises
Bad deliverable disputed -> GenLayer-verified fraud judgment
Aggressive demo policy drops reputation to 0
Agent status becomes flagged
```

## Marketplace Integration

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

RepLayer supplies facts, evidence, judgments, risk assessments, and recommendations. Marketplaces own the final policy decision.

See [docs/integration-guide.md](docs/integration-guide.md) for the longer integration path.
