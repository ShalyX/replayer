# research_trust_v6

`research_trust_v6` adds delegation accountability to the due-process-aware `research_trust_v5` projection.

## Final liability weight

A finalized `LIABILITY_APPORTIONED` event starts with a full-case impact of:

```text
trust: -30
risk:  +45
```

Each agent receives the full-case impact multiplied by its immutable `responsibility_bps`. Integer scaling uses half-up rounding. A 30/70 allocation therefore produces:

```text
Delegator: -9 trust, +14 risk
Worker:   -21 trust, +32 risk
```

Provisional responsibility uses 25% of the allocated impact. An appealed provisional judgment uses 12.5%. Once a finalized liability event exists for the case, provisional impact is removed.

A worker receives one fraud incident only when a finalized fabricated-sources case assigns at least 5,000 basis points to the worker. Risk at or above 35 produces `review`; risk at or above 60 produces `flagged`.

The same ordered event stream must always produce the same projection.

