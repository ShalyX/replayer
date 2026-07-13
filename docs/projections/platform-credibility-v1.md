# platform_credibility_v1

Platform credibility is derived from append-only identity, attestation, confirmation, challenge, and GenLayer judgment events.

- Initial credibility: 50
- Verified marketplace identity: +15
- Issued attestations: +1 each, capped at +10
- Counterparty confirmations: +3 each, capped at +15
- Valid GenLayer judgment: +5
- Challenge opened: -2
- Partially overturned attestation: an additional -10
- False attestation: an additional -23
- Inconclusive judgment: an additional -3

Scores are clamped to 0-100. Status is `trusted` at 75+, `established` at 60+, `developing` at 35+, and `restricted` below 35.

The score is snapshotted into each new attestation as `issuer_credibility_bps` with `platform_credibility_v1`. Future platform outcomes do not retroactively alter that event's contribution.
