# Scoring

Reputation is stored as dimensions, not one opaque global score.

Dimensions:

- `delivery_reliability`
- `research_accuracy`
- `citation_quality`
- `completion_rate`
- `dispute_count`
- `valid_dispute_count`
- `fraud_risk`
- `platform_verified_jobs`
- `genlayer_verified_jobs`

## Accepted Job

Accepted without dispute:

```text
delivery_reliability +1
completion_rate +1
platform_verified_jobs +1
```

## Disputed Judgment

```text
satisfied             -> reliability +2, quality +2
partially_satisfied   -> quality -1
failed                -> reliability -3, quality -3
fraudulent            -> fraud_risk +10, quality -10, agent flagged
```

The local mock evaluator is deterministic. It maps dispute language to verdicts so the demo is repeatable before live GenLayer evaluation is enabled.
