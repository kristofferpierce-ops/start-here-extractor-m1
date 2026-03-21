# Milestone 5C Block 1 Notes

This block starts Milestone 5C as the first generalized ingestion-backbone layer.

## What is included
- Generic ingestion journal records for `raw`, `normalized`, `matched`, `approved`, and `applied`
- Deterministic ingestion event IDs based on source identity plus evidence fingerprints
- Relationship memory keys that preserve provenance without hard-coding ZIP-only semantics
- Journal and rollup builder script for inventory JSONL artifacts
- Dedicated tests for ingestion record shape, deterministic identity, journal writing, and rollup output

## Why this is the safest M5C starting point
- It preserves stable evidence IDs and existing inventory records as source truth.
- It adds a connector-neutral spine instead of a ZIP-only extension.
- It keeps secrets out of journal artifacts by reusing redaction helpers.
- It leaves matching, approval, and application states pending until future connectors and operator review logic are added.

## What is intentionally not included yet
- FreshBooks connector
- communications connector migration
- canonical fact tables
- expected-versus-actual reporting
- automated matching or apply logic

## Recommended next M5C step
Build relationship memory and operator review queue scaffolding so future sources can move from `normalized` to `matched` and `approved` without breaking provenance or auditability.
