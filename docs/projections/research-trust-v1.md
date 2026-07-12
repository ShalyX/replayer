# research_trust_v1

Initial trust is 70 and initial risk is 10. `JOB_ACCEPTED` adds 4 trust. The first dispute-bearing event for each unique dispute adds 8 risk and increments disputes once; this may be `DISPUTE_OPENED`, `JUDGMENT_PROVISIONAL`, or `JUDGMENT_FINALIZED` during a contract-only replay. A finalized GenLayer judgment applies: satisfied +5 trust/-5 risk; partially satisfied -5/+8; failed -15/+20; fraudulent -30/+45 and one fraud incident. `AGENT_CLEARED` adds 10 trust and removes 20 risk.

Scores are clamped to 0-100. Status is `flagged` with any fraud incident or risk >= 60, `review` at risk >= 35, otherwise `active`. Fraud does not automatically force trust to zero.

The projection is deterministic, versioned, and reproducible from the same ordered event stream. Changing weights requires a new projection version.
