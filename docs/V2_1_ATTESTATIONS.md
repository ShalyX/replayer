# RepLayer V2.1: Attestations and Challenges

RepLayer V2.1 lets marketplaces contribute bounded work-history claims while giving agents and counterparties a live GenLayer challenge path.

## Event sequence

```text
REPUTATION_ATTESTED
COUNTERPARTY_CONFIRMED
EVENT_CHALLENGED
ATTESTATION_JUDGMENT_FINALIZED
EVENT_SUPERSEDED
REPUTATION_ATTESTED (GenLayer-corrected replacement)
```

No event is edited. The projection resolves references to determine which claims remain active.

## Authority

Platforms author reported attestations. Counterparties author confirmation events. GenLayer is authoritative for challenge outcomes, supersession, and corrected replacement values. Postgres indexes these events and computes versioned projections; it does not own the judgment.

## Anti-inflation controls

Claims require evidence, values are capped, contributions use diminishing returns, each provenance tier has a maximum contribution, challenged claims are discounted, and superseded claims have zero active weight.

## Recovery

Run `npm run ledger:rebuild-test`. The command deletes all projection rows, replays the append-only event ledger, and fails unless both V1 and V2 projections reproduce exactly.
