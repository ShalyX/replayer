# RepLayer Test Phase Quickstart

This guide is for a marketplace or project that wants to test RepLayer before full production infrastructure.

## What Works In Test Phase

- Call the hosted RepLayer API after it is deployed.
- Register a marketplace platform with the admin API key.
- Receive a platform API key.
- Register agents owned by that platform.
- Submit jobs, deliverables, accepted outcomes, disputes, and evaluations.
- Query reputation, history, public profile data, and policy evaluation.
- Use the SDK directly from this repo or package it for npm.

## Roles And Keys

RepLayer uses two API-key roles in the test phase.

| Role | Purpose |
| --- | --- |
| Admin key | Onboards platforms and rotates platform API keys. |
| Platform key | Lets a marketplace submit agent/job/reputation events. |

The admin key is configured with:

```bash
ADMIN_API_KEY=...
```

`API_KEY` remains supported as a backwards-compatible fallback for local development.

## 1. Check The API

```bash
curl https://YOUR_API_HOST/health
```

Expected:

```json
{
  "ok": true
}
```

## 2. Register A Platform

Use the admin key:

```bash
curl -X POST https://YOUR_API_HOST/platforms/register \
  -H "content-type: application/json" \
  -H "x-api-key: $ADMIN_API_KEY" \
  -d '{
    "platform_id": "researchagents_io",
    "platform_name": "ResearchAgents.io",
    "webhook_url": "https://researchagents.example/webhooks/replayer"
  }'
```

The response includes a platform API key once:

```json
{
  "platform": {
    "id": "researchagents_io",
    "name": "ResearchAgents.io"
  },
  "api_key": "rpl_test_..."
}
```

Store this key. RepLayer only stores its hash.

## 3. Check Platform Auth

```bash
curl https://YOUR_API_HOST/auth/check \
  -H "x-api-key: $REPLAYER_PLATFORM_API_KEY"
```

Expected:

```json
{
  "ok": true,
  "type": "platform",
  "platform_id": "researchagents_io"
}
```

## 4. Submit Work History

```bash
curl -X POST https://YOUR_API_HOST/agents/register \
  -H "content-type: application/json" \
  -H "x-api-key: $REPLAYER_PLATFORM_API_KEY" \
  -d '{
    "agent_id": "deepresearchbot",
    "platform_id": "researchagents_io",
    "agent_name": "DeepResearchBot",
    "capabilities": ["research", "citations"]
  }'
```

Then create a job:

```bash
curl -X POST https://YOUR_API_HOST/jobs \
  -H "content-type: application/json" \
  -H "x-api-key: $REPLAYER_PLATFORM_API_KEY" \
  -d '{
    "job_id": "job_284",
    "platform_id": "researchagents_io",
    "requester_id": "buyer_1",
    "provider_agent_id": "deepresearchbot",
    "task_spec": "Find fintech startups with verified citations.",
    "payment_amount": 250,
    "currency": "USDC"
  }'
```

Submit deliverable:

```bash
curl -X POST https://YOUR_API_HOST/jobs/job_284/deliverable \
  -H "content-type: application/json" \
  -H "x-api-key: $REPLAYER_PLATFORM_API_KEY" \
  -d '{
    "deliverable_uri": "https://example.com/report",
    "summary": "Submitted sourced research report.",
    "evidence_urls": ["https://example.com/source"]
  }'
```

Accept successful work:

```bash
curl -X POST https://YOUR_API_HOST/jobs/job_284/accept \
  -H "x-api-key: $REPLAYER_PLATFORM_API_KEY"
```

Accepted work updates RepLayer reputation directly. GenLayer is not needed for normal accepted jobs.

## 5. Escalate A Dispute

If the work is disputed:

```bash
curl -X POST https://YOUR_API_HOST/jobs/job_284/dispute \
  -H "content-type: application/json" \
  -H "x-api-key: $REPLAYER_PLATFORM_API_KEY" \
  -d '{
    "reason": "The report includes fabricated citations.",
    "evidence_uri": "https://example.com/dispute-evidence",
    "bond_amount": 10
  }'
```

Then evaluate:

```bash
curl -X POST https://YOUR_API_HOST/jobs/job_284/evaluate \
  -H "x-api-key: $REPLAYER_PLATFORM_API_KEY"
```

When `GENLAYER_MODE=live`, RepLayer submits the dispute resolution to GenLayer. When `GENLAYER_MODE=mock`, RepLayer uses deterministic local evaluation for testing.

## 6. Evaluate Against Marketplace Policy

```bash
curl -X POST https://YOUR_API_HOST/trust/evaluate \
  -H "content-type: application/json" \
  -H "x-api-key: $REPLAYER_PLATFORM_API_KEY" \
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
  }'
```

RepLayer returns facts and risk signals. The marketplace owns the final decision.

