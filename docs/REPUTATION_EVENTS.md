# Reputation Events

The canonical ledger is `reputation_events`. Events are append-only and identified by globally unique `rep_evt_*` IDs.

Supported lifecycle events include `AGENT_REGISTERED`, `JOB_CREATED`, `DELIVERABLE_SUBMITTED`, `JOB_ACCEPTED`, `DISPUTE_OPENED`, `JUDGMENT_PROVISIONAL`, `JUDGMENT_FINALIZED`, `FRAUD_CONFIRMED`, `AGENT_CLEARED`, `EVENT_ATTESTED`, `EVENT_CHALLENGED`, `EVENT_SUPERSEDED`, and `POLICY_EVALUATED`.

Provenance is one of `platform_reported`, `counterparty_confirmed`, `genlayer_provisional`, `genlayer_verified`, `challenged`, or `superseded`. Verification lifecycle is `pending`, `provisional`, `finalized`, `appealed`, or `superseded`.

GenLayer provenance is valid only when contract address and transaction hash are present. Events are never updated or deleted; corrective events reference the event they challenge or supersede.
