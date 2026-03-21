# Milestone 5C Block 5 Notes

This block adds the first generic adapter-execution contract scaffold for records already in the `applied` state.

## Delivered
- connector-neutral adapter catalog normalization
- deterministic adapter execution contract generation for applied records
- adapter contract review queue for no-match and ambiguous adapter routing cases
- adapter contract rollup and markdown summaries
- a builder script for producing contract artifacts from applied projections

## Why this shape
The apply layer from Block 4 remained intentionally projection-based. This block adds the next bridge without hard-coding a single downstream system. Instead of executing side effects directly, it emits explicit adapter contracts that can later be handed to real target-specific executors.

## Guardrails preserved
- stable evidence refs remain intact
- provenance stays attached to each contract
- secret-bearing fields are redacted before serialization
- adapter selection stays catalog-driven and explainable
- unresolved adapter routing stays visible in a review queue instead of silently defaulting
