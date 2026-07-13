# research_trust_v5

`research_trust_v5` adds due-process weighting to the identity-aware `research_trust_v4` Passport.

## Provisional impact

| Verdict | Trust | Risk |
| --- | ---: | ---: |
| satisfied | +1 | -1 |
| partially_satisfied | -1 | +2 |
| failed | -4 | +6 |
| fraudulent | -8 | +12 |
| inconclusive | 0 | +2 |

An active appeal applies 50% of the provisional impact, rounded toward zero. Provisional fraud does not increment `fraud_incidents`.

Once `JUDGMENT_FINALIZED` exists, the provisional adjustment is removed. Final impact comes from the finalized judgment rules inherited through `research_trust_v4`. Superseded events have zero active weight.

Inputs are the ordered reputation event stream and event references. The same ledger always produces the same trust score, risk score, status, fraud count, provisional impacts, and judgment lifecycle.
