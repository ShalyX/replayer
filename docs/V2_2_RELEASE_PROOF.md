# RepLayer V2.2 Release Proof

Verified live on GenLayer StudioNet on 2026-07-13 without mock data.

## Deployment

- Contract: `0xE66B9A95F0439A416274A2a21df46e76b57d176A`
- Deployment transaction: `0x8ad3658b095f8961ec280a0c3084c6988a63e6a54a2d2c1ade2cb5addf416e8b`
- Platform projection: `platform_credibility_v1`
- Agent projection: `research_trust_v3`

## Live credibility story

- Reliable Market: `reliable_market_1783906197`
- Inaccurate Market: `inaccurate_market_1783906197`
- Reliable issuer credibility before new claim: 77 (`trusted`)
- Inaccurate issuer credibility before new claim: 26 (`restricted`)
- Inaccurate issuer challenge-overturn rate: 100%
- False-attestation judgment transaction: `0xb6b80a539b28c63526551b386a7fd61bedd7643f6b0f8d39afd698a67f15197a`

Both platforms then reported the same 50 completed jobs for new agents. The events recorded immutable credibility snapshots:

| Issuer | Snapshot | Contribution | Agent trust |
| --- | ---: | ---: | ---: |
| Reliable Market | 7700 bps | +6 | 76 |
| Inaccurate Market | 2600 bps | +3 | 73 |

Later events moved the current platform scores to 78 and 27 respectively, but the historical attestation contributions remained 6 and 3 because V3 uses the recorded snapshots.

## Replay proof

The production rebuild deleted and recreated 48 agent projection rows and all platform credibility projections. Before and after were identical:

```text
candidate_a trust=76 issuer_snapshot=7700 contribution=6
candidate_b trust=73 issuer_snapshot=2600 contribution=3
reliable_platform current_credibility=78
inaccurate_platform current_credibility=27
```

This proves that platform credibility, agent trust, and historical issuer weighting are reproducible from the append-only ledger without circular retroactive scoring.
