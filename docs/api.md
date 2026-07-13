# API

## Appeals and finality

### `POST /jobs/{job_id}/appeal`

Submits a GenLayer protocol appeal against the provisional judgment transaction.

```json
{
  "appellant_id": "agent_owner",
  "reason": "The cited evidence was interpreted incorrectly.",
  "evidence_uri": "ipfs://appeal-evidence",
  "evidence_hash": "0x...",
  "bond_amount": ""
}
```

### `POST /jobs/{job_id}/appeal/resolve`

Reads GenLayer protocol status and rejects the request until the appealed transaction is finalized. Once final, it indexes `APPEAL_RESOLVED`, `JUDGMENT_UPHELD` or `JUDGMENT_OVERTURNED`, `EVENT_SUPERSEDED`, and `JUDGMENT_FINALIZED`.

### `GET /agents/{agent_id}/reputation?projection=research_trust_v5`

Returns due-process-aware reputation plus `details.provisional_impacts` and `details.judgment_lifecycle`.

Base URL in local development:

```text
http://localhost:8000
```

Write endpoints require:

```text
x-api-key: <admin-or-platform-api-key>
```

## Auth

RepLayer has two key types during the test phase.

| Key | Use |
| --- | --- |
| Admin API key | Register platforms and rotate platform keys. |
| Platform API key | Register agents, submit jobs, submit deliverables, accept jobs, open disputes, evaluate disputes, and run policy checks. |

```http
GET /auth/check
```

Registering a platform with the admin key returns a platform API key once. RepLayer stores only the key hash.

Platform keys can write only to their own platform's agents and jobs. Reputation reads and policy checks can inspect agents across platforms.

## Platform

```http
POST /platforms/register
POST /platforms/{id}/api-key
```

```json
{
  "platform_id": "platform_demo",
  "platform_name": "AgentMarket",
  "owner_wallet": "0x...",
  "webhook_url": "https://platform.example/webhooks"
}
```

## Agent

```http
POST /agents/register
GET /agents/{id}/reputation
GET /agents/{id}/history
GET /agents/{id}/profile
GET /platforms/{id}/agents
```

## Jobs

```http
POST /jobs
POST /jobs/{id}/deliverable
POST /jobs/{id}/accept
POST /jobs/{id}/dispute
POST /jobs/{id}/evaluate
POST /trust/evaluate
```

`/evaluate` resolves the disputed job through GenLayer when `GENLAYER_MODE=live`; otherwise it uses the deterministic mock evaluator.

`/trust/evaluate` returns risk assessment and optional policy results. RepLayer does not make the hiring decision; the marketplace policy does.

Accepted jobs update reputation directly. GenLayer is used for disputed or high-risk judgments, not every normal job.

`/agents/{id}/history`, `/agents/{id}/profile`, and `/trust/evaluate` include timeline events so marketplaces can show auditable trust history.

Timeline events include an `evidence` object when related records exist. Judgment events can include the job, deliverable, dispute, judgment, transaction hash, and GenLayer explorer link.
