# RepLayer V2.4 Release Proof

## Deployment

- Network: GenLayer StudioNet
- Contract: `0xBf42bB13fb77695d42B08eCdf589Ba54eB1C361A`
- Deployment transaction: `0x5dfcbff75ceb0ed214af521c540fb288f2bba448d416c708156219ed02b3e1c8`
- Contract schema readback: successful

## Live appeal

- Agent: `appealable_agent_1783977812`
- Job: `appealable_job_1783977812`
- Dispute: `appealable_dispute_1783977812`
- Judgment transaction: `0xc46455b2b51fecd23b4182092a7d11f9656c71ceb888c6dc6d9aa6cf84c15610`
- Protocol round: `1`
- Appeal outcome: `JUDGMENT_UPHELD`
- Final verdict: `inconclusive`
- Final contract event: `rep_evt_appeal_final_4ecce3b57968ca52d795254e`
- Ledger recording transaction: `0xb97d43331f7216afe9ea5abbca8e6af699c441c1835dc050462ffde84a5752d9`
- Final `research_trust_v5`: trust `70`, risk `18`

The final event was read back from contract state with `genlayer_verified` provenance, `finalized` status, the provisional event reference, the appeal event reference, the resolution event reference, and the upheld outcome reference.

## Recovery

- Indexer health: healthy
- Indexer lag: `0`
- Last indexed event: `rep_evt_appeal_final_4ecce3b57968ca52d795254e`
- Ledger verification: `72` authoritative append-only events; `16` legacy rows quarantined
- Destructive replay: deterministic for `75` agent, `15` platform, and `19` identity projections

The live acceptance used no mock verdict and no deterministic backend fallback.
