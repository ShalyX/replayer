# RepLayer V2.1 Release Proof

Verified live on GenLayer StudioNet on 2026-07-13 without mock verdicts.

## Deployment

- Contract: `0xbdD374187888Bf98E2C665162b20340Cc8Fb1930`
- Deployment transaction: `0x01a16045c350f04994e7c19cabb4bc816761e1c63ead5aa88968c1fdb2ab5a02`
- Projection: `research_trust_v2`

## Acceptance run

- Agent: `researchpro_1783904710`
- Marketplace A attestation: `rep_evt_attestation_fb7f158d5e9d`
- Marketplace B confirmation: `rep_evt_confirmation_cd52756ca728`
- Challenge: `rep_evt_challenge_3f7e2dd89282`
- Final judgment: `rep_evt_attestation_judgment_2ea580ec007a`
- Supersession: `rep_evt_superseded_0d27d050162d`
- Corrected attestation: `rep_evt_attestation_corrected_add47da83b77`
- Challenge transaction: `0xb5f4b87a842cc084489626e7c5bee2bcf043ed0a96d02950d23cb91daaaf89db`

GenLayer returned `attestation_partially_valid` with confidence 9800 basis points and a corrected valid value of 32.

## Projection effect

| State | Trust | Active work history |
| --- | ---: | --- |
| Marketplace A reports 50 | 76 | 50 platform reported |
| Marketplace B confirms 30 | 81 | 50 reported + 30 confirmed |
| GenLayer correction finalizes | 78 | 32 GenLayer verified |

The original 50-job claim and the 30-job confirmation both remain visible with `superseded` provenance and zero contribution.

## Indexer proof

The hosted indexer reported healthy on the V2.1 contract with last event `rep_evt_attestation_corrected_add47da83b77`. Every challenge-produced event contains contract readback provenance and transaction `0xb5f4...89db`.

## Replay proof

The production admin rebuild deleted and recreated 24 V1/V2 projection rows. Before and after were identical:

```text
trust=78 risk=10 status=active valid_jobs=32
reported_50=superseded confirmation_30=superseded corrected_32=genlayer_verified
```

This demonstrates that Marketplace C's Passport is reproducible from the append-only ledger after projection deletion.
