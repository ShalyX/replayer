# research_trust_v3

V3 retains V1 job and judgment behavior and V2 attestation supersession, then weights new reported and confirmed attestations using an immutable platform-credibility snapshot.

For platform-reported work, the cap is `2 + floor(credibility_bps * 6 / 10000)`, clamped to 1-8. Counterparty-confirmed work uses a 1-6 cap. GenLayer-corrected replacement events remain high-authority and cap at 10.

The event stores both `issuer_credibility_bps` and `credibility_projection_version`. Replay therefore uses the historical snapshot rather than today's platform score, preventing circular retroactive changes.
