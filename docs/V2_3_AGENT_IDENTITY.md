# RepLayer V2.3: Agent Identity and Sybil Resistance

RepLayer V2.3 makes agent identity an event-sourced graph. Platform-local agent IDs and chain-qualified controllers resolve to one canonical Passport only after cryptographic controller proof or a finalized GenLayer identity judgment.

## Authority boundary

- RepLayer verifies deterministic EVM and Solana signatures over canonical identity messages.
- GenLayer is authoritative for challenged identity-binding outcomes.
- Postgres stores indexed events and disposable `agent_identity_v1` and `research_trust_v4` projections.
- No endpoint mutates a canonical identity, alias list, or merged score directly.

## Events

```text
AGENT_IDENTITY_REGISTERED
IDENTITY_BINDING_PROPOSED
CONTROLLER_CONFIRMED
IDENTITY_LINKED
IDENTITY_CHALLENGED
IDENTITY_JUDGMENT_FINALIZED
IDENTITY_LINK_FINALIZED
IDENTITY_LINK_REJECTED
IDENTITY_UNLINKED
IDENTITY_CONTROLLER_ROTATED
IDENTITY_OWNERSHIP_TRANSFERRED
```

Every correction is a new event. Rejected, unlinked, or superseded bindings have zero graph weight.

## Signing messages

Registration:

```text
RepLayer identity registration
agent:{agent_id}
identity:{normalized_identity}
nonce:{nonce}
```

Linking:

```text
RepLayer identity link
source:{source_agent_id}
target:{target_agent_id}
nonce:{nonce}
```

EVM identities use `base:0x...` or `eip155:{chain_id}:0x...`. Solana identities use `solana:{public_key}`. Raw signatures are verified in memory; append-only events retain proof hashes rather than reusable signature material.

## API

- `POST /agents/{agent_id}/identities`
- `POST /identity-bindings`
- `POST /identity-bindings/{proposal_event_id}/confirm`
- `POST /identity-bindings/{proposal_event_id}/challenge`
- `GET /agents/{agent_id}/identity`
- `GET /identities/resolve?identity={chain-qualified-identity}`

Both platform-local aliases return `research_trust_v4`, which aggregates the linked component once and exposes the same canonical Passport.
