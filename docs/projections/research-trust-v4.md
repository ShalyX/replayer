# research_trust_v4

`research_trust_v4` is the identity-aware Passport projection.

It consumes `agent_identity_v1` and each linked member's reproducible `research_trust_v3` projection:

```text
trust = clamp(70 + sum(member_trust - 70), 0, 100)
risk  = clamp(10 + sum(member_risk - 10), 0, 100)
```

Jobs, successes, disputes, and fraud incidents are summed across component members. Work-history events and verified platforms are combined. Every alias in the component receives the same canonical trust and risk outcome.

The single 70/10 baseline prevents identity linking from minting reputation. A newly linked identity with no history contributes zero delta. A flagged alias cannot escape its negative history by querying another linked alias.
