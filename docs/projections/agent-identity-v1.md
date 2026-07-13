# agent_identity_v1

`agent_identity_v1` deterministically rebuilds the canonical agent graph from reputation events.

## Rules

- Every registered agent begins as a one-node component.
- `IDENTITY_LINKED` and `IDENTITY_LINK_FINALIZED` join source and target components.
- `IDENTITY_LINK_REJECTED`, `IDENTITY_UNLINKED`, and `EVENT_SUPERSEDED` deactivate referenced links or proposals.
- Pending proposals and challenges never join components.
- The earliest identity registration in ledger order remains canonical; agent ID is the deterministic tie-breaker.
- Registered chain identities and platform-local IDs become resolvable aliases.
- Controller rotation and ownership transfer preserve prior event history; they never rewrite registration events.

Given the same ordered event ledger, the canonical ID, members, aliases, controllers, challenge count, and rejected-binding count are identical.
