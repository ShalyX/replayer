# Reputation Scoring Policy

RepLayer reputation changes event by event.

## What Updates Reputation?

| Event | GenLayer Required? | Reputation Effect |
| --- | --- | --- |
| Job accepted | No | Trust increases gradually. |
| Deliverable submitted | No | Adds timeline evidence, but does not change score by itself. |
| Dispute opened | No | Risk increases slightly while the dispute is unresolved. |
| Dispute judged satisfied | Yes in live mode | Trust can recover or improve. |
| Dispute judged failed | Yes in live mode | Trust decreases. |
| Dispute judged fraudulent | Yes in live mode | Trust drops sharply, fraud risk rises, agent can become flagged. |
| Marketplace policy check | No | Adds an evidence event, but marketplace owns the decision. |

## Why GenLayer Is Not Used For Every Job

Successful jobs are first-party marketplace attestations. If a buyer accepts the work and there is no dispute, RepLayer can record that accepted outcome directly.

GenLayer is used for contested or high-risk claims, especially fraud judgments. That keeps the validator work focused on cases where independent judgment matters.

## Current Test-Phase Formula

RepLayer stores cumulative counters and computes the public score from the latest snapshot:

```text
overall =
  70
  + delivery_reliability * 4
  + completion_rate * 3
  + research_accuracy * 2
  + citation_quality * 2
  - fraud_risk * 8
  - valid_dispute_count * 5
```

The result is clamped from `0` to `100`.

## Positive Events

Accepted work currently applies:

```json
{
  "delivery_reliability": 1,
  "completion_rate": 1,
  "platform_verified_jobs": 1
}
```

This means successful work builds trust over time.

## Negative Events

Opening a dispute applies:

```json
{
  "dispute_count": 1
}
```

A fraudulent judgment applies:

```json
{
  "delivery_reliability": -5,
  "research_accuracy": -10,
  "citation_quality": -10,
  "valid_dispute_count": 1,
  "fraud_risk": 10
}
```

The current demo intentionally treats verified fraud as severe to make the trust collapse obvious. Future versions should add more nuanced weighting, severity levels, recovery, source reliability, and time decay.

## Policy Evaluation

Marketplace policy is submitted inline to `/trust/evaluate` during the test phase:

```json
{
  "min_trust_score": 70,
  "max_risk_score": 30,
  "max_fraud_incidents": 0,
  "allow_flagged": false
}
```

Saved marketplace policies are a later product feature. For now, each marketplace sends its policy with the evaluation request.

