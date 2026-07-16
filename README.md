# RepLayer

Portable accountability for AI agents, verified by GenLayer.

RepLayer lets agent marketplaces share event-sourced trust. GenLayer verifies disputed work, reputation attestations, and identity links; every integrated platform can query the resulting canonical agent Passport before hiring.

V3.0 adds delegation and accountability. Signed authority, spending, subdelegation, disclosure, and output records form an inspectable supply chain; GenLayer attributes responsibility, and `research_trust_v6` applies finalized liability proportionally to each accountable agent.

The V3 contract and no-mock acceptance flow are ready for deployment. The deterministic 30/70 liability and replay proof is recorded in [docs/V3_RELEASE_PROOF.md](docs/V3_RELEASE_PROOF.md); V2.4 remains the active production contract until that deployment is completed.

## V2 Live Proof

- V2.4 appeals contract: `0xBf42bB13fb77695d42B08eCdf589Ba54eB1C361A`
- V2.4 deployment transaction: `0x5dfcbff75ceb0ed214af521c540fb288f2bba448d416c708156219ed02b3e1c8`
- V2.4 appealed judgment transaction: `0xc46455b2b51fecd23b4182092a7d11f9656c71ceb888c6dc6d9aa6cf84c15610` (round 1, upheld, finalized)
- V2.4 final ledger event: `rep_evt_appeal_final_4ecce3b57968ca52d795254e`
- V2.3 contract: `0x2E7017a0Ae4567b3398EC5C836913dce745F727e`
- V2.3 identity judgment: `0x18af1dcfe89bb8b4e2e39e5fd5476d0c6bfc85ae545caa92b7aa2f163926be99`
- Result: Base and Solana aliases resolve to one Passport; a false identity claim was rejected by GenLayer.
- V2.3 proof: [docs/V2_3_RELEASE_PROOF.md](docs/V2_3_RELEASE_PROOF.md)
- Final fraudulent judgment: `0x313e028aa5fa9ab1227ca321fa9c9c33a4c3a1ecea4aee9a219ff404f4ec07a6`
- Result: trust `74 -> 44`, risk `10 -> 63`, status `flagged`
- Full verification record: [docs/V2_RELEASE_PROOF.md](docs/V2_RELEASE_PROOF.md)

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
6. DeepResearchBot's trust score falls from 74 to 44, risk rises from 10 to 63, and status becomes flagged.
7. Another marketplace checks the public profile before hiring.
```

> V2 derives versioned trust and risk projections from the append-only reputation event ledger.

> V2.3 also derives canonical identity from signed, challengeable identity events. Linking an empty alias grants no new baseline reputation.

> V3.0 derives accountability from finalized liability events. Reputation follows responsibility across delegation chains, not merely the agent that submitted the final file.

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

- `apps/api`: FastAPI backend, Postgres projections, GenLayer indexer, and live contract adapter.
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
ADMIN_API_KEY=dev-key
GENLAYER_MODE=live
ALLOW_TEST_MOCKS=false
GENLAYER_CONTRACT_ADDRESS=0xd6B933d895dAc6c171587D47049F8bF03C0e9E34
GENLAYER_EXPLORER_BASE_URL=https://explorer-studio.genlayer.com/tx
NEXT_PUBLIC_API_BASE=http://localhost:8000
NEXT_PUBLIC_API_KEY=dev-key
```

The public runtime requires live GenLayer mode. Mocks are limited to automated tests.

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
npm run smoke:v3.0
```

Expected result:

```text
Good job accepted -> reputation rises
Bad deliverable disputed -> GenLayer-verified fraud judgment
Aggressive demo policy drops reputation to 0
Agent status becomes flagged
```

## Marketplace Integration

For the test phase, start with:

- [Test phase quickstart](docs/test-phase-quickstart.md)
- [Test phase deployment](docs/test-phase-deployment.md)
- [Reputation scoring policy](docs/scoring-policy.md)

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

The marketplace console and public profile include a reputation timeline, so trust can be audited as a history of jobs, disputes, GenLayer judgments, and policy checks rather than treated as a naked score. Each event opens an evidence explorer with the related job, deliverable, dispute, judgment, transaction hash, and GenLayer explorer link when available.

See [docs/integration-guide.md](docs/integration-guide.md) for the longer integration path.
