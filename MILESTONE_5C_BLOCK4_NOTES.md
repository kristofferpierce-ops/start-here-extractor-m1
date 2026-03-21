# Milestone 5C Block 4 Notes

This block adds the first generic `approved -> applied` transition scaffold.

## Delivered
- connector-neutral application target catalog normalization
- deterministic application queue generation for approved records
- operator application decision application for suggested, selected, deferred, and not-applicable outcomes
- application transition rollup and markdown summary
- projection JSONL and application decision journal outputs

## Why this shape
The apply layer stays generic and future-safe. It does not hard-code a single downstream tool, and it does not mutate the raw evidence stream. Instead, it projects approved records into a target-routing step that can later be connected to CRM, ticketing, ERP, or internal operating-core adapters.

## Guardrails preserved
- stable evidence refs remain intact
- provenance stays attached to each record
- secret-bearing fields are redacted before serialization
- operator decisions are journaled separately from source evidence
