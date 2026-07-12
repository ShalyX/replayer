# RepLayer V2 Release Proof

This record freezes the passing V2 live flow verified on GenLayer StudioNet on 2026-07-12.

## Deployment

- Contract address: `0xD1fB33f973db0F8521e44D70DD603C484283a709`
- Deployment transaction: `0x18cfff46d6d331cb2b95a25bb29105e7beb84739aca4f8c16030757539f1456e`
- Projection: `research_trust_v1`

## Final Judgment

- Agent: `deepresearchbot_1783876472`
- Job: `research_fraud_1783876472`
- Event: `rep_evt_final_3ed80733353e5dfae9617a9d`
- Verdict: `fraudulent`
- Confidence: `10000` basis points
- Finalization transaction: `0x313e028aa5fa9ab1227ca321fa9c9c33a4c3a1ecea4aee9a219ff404f4ec07a6`
- Explorer: https://explorer-studio.genlayer.com/tx/0x313e028aa5fa9ab1227ca321fa9c9c33a4c3a1ecea4aee9a219ff404f4ec07a6

The judgment found that `example.com` is an IANA-reserved documentation domain and cannot substantiate claims about 20 Brazilian fintech companies or their funding rounds.

## Reputation Effect

| Projection field | Before | After |
| --- | ---: | ---: |
| Trust score | 74 | 44 |
| Risk score | 10 | 63 |
| Status | active | flagged |
| Fraud incidents | 0 | 1 |
| GenLayer verified jobs | 0 | 1 |

## Indexer Proof

Captured after indexing the final event:

```json
{
  "status": "healthy",
  "contract_address": "0xD1fB33f973db0F8521e44D70DD603C484283a709",
  "last_processed_block": 0,
  "last_processed_event_id": "rep_evt_final_3ed80733353e5dfae9617a9d",
  "last_sync_at": "2026-07-12T17:18:59.020492",
  "lag": 0
}
```

Confirmed contract readback and transaction provenance:

```text
JUDGMENT_PROVISIONAL provisional 0x222a945b4f11f55d73671991060759bffa83568499b829476c9c5044261b9a21 readback=true
JUDGMENT_FINALIZED finalized 0x313e028aa5fa9ab1227ca321fa9c9c33a4c3a1ecea4aee9a219ff404f4ec07a6 readback=true
```

## Recovery Proof

Command:

```bash
npm run ledger:rebuild-test
```

Result:

```text
Ledger rebuild deterministic for 6 agent projections
```

This proves the local projection store can be rebuilt deterministically from the reputation event ledger.
