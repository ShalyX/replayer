# RepLayer V3.0: Delegation and Accountability

RepLayer V3.0 makes reputation follow responsibility through agent supply chains.

## Authority boundary

- The API indexes signed delegation scope, tools, actions, spending limits, disclosure duties, identity bindings, acceptance, subdelegation, and output evidence.
- GenLayer decides the subjective responsibility outcome and basis-point allocation.
- Postgres stores operational delegation rows and event projections. It does not own liability or reputation impact.
- `research_trust_v6` deterministically converts finalized `LIABILITY_APPORTIONED` events into distinct Passport impacts.

## Event lifecycle

```text
DELEGATION_CREATED
-> AUTHORITY_SCOPE_GRANTED
-> SPENDING_LIMIT_SET
-> DELEGATION_ACCEPTED
-> WORK_SUBDELEGATED (optional)
-> DELEGATED_OUTPUT_SUBMITTED
-> RESPONSIBILITY_DISPUTED
-> RESPONSIBILITY_JUDGMENT_PROVISIONAL
-> RESPONSIBILITY_APPEALED (optional)
-> RESPONSIBILITY_JUDGMENT_FINALIZED
-> LIABILITY_APPORTIONED
```

The contract permits `worker_primary`, `delegator_primary`, `shared_responsibility`, `unauthorized_subdelegation`, `tool_failure`, `no_fault`, and `inconclusive`. Accountable outcomes must allocate exactly `10,000` basis points. Tool failure, no fault, and inconclusive outcomes allocate zero.

## API

```text
POST /delegations
POST /delegations/{id}/accept
POST /delegations/{id}/output
GET  /delegations/{id}
POST /delegations/{id}/responsibility-dispute
POST /delegations/{id}/responsibility/finalize
POST /delegations/{id}/responsibility/appeal
POST /delegations/{id}/responsibility/appeal/resolve
```

Protocol appeals target the original `evaluate_responsibility` transaction. Finalization is rejected until GenLayer reports the transaction as finalized. There is no local verdict fallback.

## Invariants

1. Delegation records never mutate reputation directly.
2. Principal and worker receive separate liability events.
3. Final allocations originate from live GenLayer contract state.
4. Provisional and appealed liability have discounted temporary impact.
5. Final liability replaces provisional impact.
6. Replay from the event ledger reconstructs the same accountability graph and scores.

