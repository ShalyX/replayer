# Reputation Events

The canonical ledger is `reputation_events`. Events are append-only and identified by globally unique `rep_evt_*` IDs.

Supported lifecycle events also include `DELEGATION_CREATED`, `DELEGATION_ACCEPTED`, `AUTHORITY_SCOPE_GRANTED`, `SPENDING_LIMIT_SET`, `WORK_SUBDELEGATED`, `DELEGATED_OUTPUT_SUBMITTED`, `RESPONSIBILITY_DISPUTED`, `RESPONSIBILITY_JUDGMENT_PROVISIONAL`, `RESPONSIBILITY_APPEALED`, `RESPONSIBILITY_JUDGMENT_FINALIZED`, and `LIABILITY_APPORTIONED`.

Provenance is one of `platform_reported`, `counterparty_confirmed`, `genlayer_provisional`, `genlayer_verified`, `challenged`, or `superseded`. Verification lifecycle is `pending`, `provisional`, `finalized`, `appealed`, or `superseded`.

GenLayer provenance is valid only when contract address and transaction hash are present. Events are never updated or deleted; corrective events reference the event they challenge or supersede.
