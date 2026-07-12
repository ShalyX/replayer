# GenLayer Source of Truth

For disputed jobs, the API submits evidence to the configured live contract and waits for contract readback. If the write or read fails, the API returns an error or pending response and creates no local verdict.

Only contract-read events may use `genlayer_provisional` or `genlayer_verified`. The UI may display “Verified by GenLayer” only when the indexed event contains both `contract_address` and `transaction_hash`.

Legacy `judgments` rows remain an indexed compatibility cache. They are not authoritative. `ALLOW_TEST_MOCKS` defaults to false and may be enabled only by automated tests.
