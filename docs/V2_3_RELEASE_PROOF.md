# RepLayer V2.3 Release Proof

Verified on GenLayer StudioNet on 2026-07-13 without mock data.

## Deployment

- Contract: `0x2E7017a0Ae4567b3398EC5C836913dce745F727e`
- Deployment transaction: `0xa5f268250c68ebc0f6377b38a6c55d601d1622c50af44a43c1dcddff83da816e`
- Identity projection: `agent_identity_v1`
- Passport projection: `research_trust_v4`
- Validator execution: `SUCCESS`, majority agree

The deployed schema exposes `confirm_identity_binding` and `challenge_identity_binding`. `get_event_count` returned `0` immediately after deployment.

## Deterministic link readback

- Proposal event: `rep_evt_v23_probe_proposal_1783936782`
- Proposal transaction: `0xe9f9bdf140afc904c17fe255f0895bbf329262b1d2e6e0c1dffcd0989f045402`
- Link event: `rep_evt_v23_probe_link_1783936782`
- Link transaction: `0xd07affaacf5c7dad0a6aa13c1347358853db790f8831493e54c66e5751f90d90`
- Contract readback: confirmed

## GenLayer challenge readback

- Challenge transaction: `0x369f8d03207ba45626e40dd6b273c2cfad301ebfbd800d0bbd0278ba9e42a34e`
- Judgment event: `rep_evt_v23_probe_judgment_1783936853`
- Resolution event: `rep_evt_v23_probe_resolution_1783936853`
- Outcome: `inconclusive`
- Resolution: `IDENTITY_LINK_REJECTED`

The inconclusive outcome correctly failed closed: insufficient common-control evidence did not enter the canonical identity graph.

## Local acceptance and replay

The V2.3 smoke test verifies real EVM message recovery and Solana Ed25519 signatures, links two legitimate aliases, rejects a false claimant, and rebuilds the identity graph after deleting projections:

```text
V2.3 passed: aliases linked, canonical trust=77, false identity rejected, replay identical
```

The repository-wide recovery test also passed:

```text
Ledger rebuild deterministic for 48 agent, 12 platform, and 16 identity projections
```

Contract-aware ledger verification passed across V2.2 and V2.3:

```text
Ledger verified: 54 authoritative append-only events; 16 quarantined legacy rows
```

## Full live API acceptance

The resumable live runner completed the cross-platform sequence through the REST API:

- Canonical agent: `base_agent_1783937207`
- Linked alias: `solana_agent_1783937207`
- Canonical trust through either alias: `74`
- Valid link transaction: `0x4138aa434043a59e9f717a9fd6bd6d2d677975c06f64628c914163c6b09b511f`
- False-link judgment transaction: `0x18af1dcfe89bb8b4e2e39e5fd5476d0c6bfc85ae545caa92b7aa2f163926be99`
- GenLayer outcome: `identity_link_false`
- Resolution: `IDENTITY_LINK_REJECTED`
- Rebuilt projections: `64`

Marketplace C can query either platform-local agent ID and receive the same canonical Passport. The false claimant remains a separate one-agent component.
