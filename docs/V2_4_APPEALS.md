# RepLayer V2.4: Appeals and Due Process

V2.4 models GenLayer judgment finality explicitly. An accepted validator result is provisional reputation evidence, not permanent truth.

## Authority boundary

- GenLayer Optimistic Democracy owns appeal eligibility, validator expansion, re-execution, and transaction finality.
- The Intelligent Contract owns the dispute judgment and final appeal-resolution events.
- RepLayer indexes accepted and finalized observations, preserves superseded provisional history, and builds disposable projections.
- Postgres never invents or directly mutates a verdict.

## Lifecycle

```text
JUDGMENT_PROVISIONAL
-> APPEAL_SUBMITTED
-> APPEAL_RESOLVED
-> JUDGMENT_UPHELD | JUDGMENT_OVERTURNED
-> EVENT_SUPERSEDED
-> JUDGMENT_FINALIZED
```

`APPEAL_SUBMITTED` targets the original GenLayer judgment transaction. GenLayer re-executes that transaction through its protocol appeal process. RepLayer resolves the appeal only after the protocol transaction reports `FINALIZED`, then reads the recomputed contract judgment and records the outcome on-chain.

The backend uses `genlayer-js` for non-interactive appeal and finalization writes. It accepts either `GENLAYER_PRIVATE_KEY` or the encrypted GenLayer CLI keystore plus `GENLAYER_ACCOUNT_PASSWORD`; secrets are never written to the ledger.

## API

```text
POST /jobs/{job_id}/appeal
POST /jobs/{job_id}/appeal/resolve
POST /jobs/{job_id}/evaluate
```

`/evaluate` is the no-appeal finalization path. It rejects accepted-but-not-final GenLayer transactions. The appeal path rejects duplicate appeals, finalized transactions, and duplicate resolutions.

## Public claims

Passport lifecycle entries include event provenance, verification status, contract address, transaction hash, references, and occurrence time. A provisional or appealed event is never labeled finalized.

## Recovery

`npm run ledger:rebuild-test` deletes projections and reconstructs `research_trust_v5` from reputation events. Superseded provisional observations remain in the timeline but contribute no active final weight.
