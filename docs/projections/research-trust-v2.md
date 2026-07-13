# research_trust_v2

V2 preserves every V1 job and judgment rule, then derives additional trust from active work-history attestations.

## Attestation rules

- Only `jobs_completed` is supported initially.
- Both `evidence_uri` and `evidence_hash` are required.
- Values are capped at 10,000 before projection.
- Diminishing returns use `floor(sqrt(value))`.
- Platform-reported contribution is capped at 6 trust points.
- Counterparty-confirmed contribution is capped at 5 trust points.
- GenLayer-verified contribution is capped at 10 trust points and receives a 3-point provenance premium.
- A challenged claim contributes half weight until finalized.
- A superseded claim and confirmations referencing it contribute zero.
- A corrected GenLayer replacement is the only active claim after partial validation.

For the acceptance story, a reported value of 50 moves trust from 70 to 76. A confirmation of 30 moves it to 81. When GenLayer supersedes both with a verified value of 32, the reproducible final trust score is 78.

Changing these rules requires `research_trust_v3`; V1 and V2 remain reproducible.
