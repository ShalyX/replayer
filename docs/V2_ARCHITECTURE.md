# RepLayer V2 Architecture

RepLayer is an event-sourced trust network for AI agents, using GenLayer to turn disputed outcomes into consensus-backed reputation events.

## Authority boundary

GenLayer is authoritative for disputed-work judgments, judgment lifecycle state, challenges, appeals, supersession, and verified reputation events. RepLayer indexes those events in Postgres and computes versioned projections. Postgres rows, legacy judgments, Passport responses, scores, risk values, and policy outcomes are caches or derived views.

## Write path

Marketplace -> RepLayer API -> GenLayer Intelligent Contract -> append-only event finalized.

## Read path

GenLayer contract -> indexer checkpoint -> `reputation_events` -> projection replay -> Passport, timeline, SDK, and marketplace policy.

Platform lifecycle events may be platform-reported. Dispute verdicts require GenLayer. A database can be rebuilt by resetting the indexer checkpoint, re-indexing contract events, and replaying every active projection version.

No contract method stores or mutates an official trust score. Corrections append challenge, clearance, or supersession events referencing earlier events.
