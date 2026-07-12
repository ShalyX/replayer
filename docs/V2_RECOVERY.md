# V2 Recovery

1. Stop API writes and the indexer.
2. Back up Postgres.
3. Delete `agent_reputation_projections` and indexed `reputation_events` only after recording the current checkpoint.
4. Reset `indexer_checkpoints` to `GENLAYER_START_BLOCK`.
5. Run `npm run indexer:once` until lag is zero.
6. Run `npm run ledger:verify`.
7. Run `npm run projections:rebuild`.
8. Run `npm run ledger:rebuild-test` and compare Passport output.

Never reconstruct missing GenLayer judgments from deliverable text or dispute language. A failed contract read leaves the judgment pending.
