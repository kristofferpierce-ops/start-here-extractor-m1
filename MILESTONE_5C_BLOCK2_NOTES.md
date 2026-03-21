# Milestone 5C block 2 notes

This block adds deterministic relationship-memory grouping and an operator review queue on top of the Block 1 ingestion journal.

## What it adds
- `start_here_extractor.relationship_memory` for component grouping, candidate entity IDs, and queue generation
- `scripts/build_relationship_memory.py` for building relationship memory and operator review artifacts from ingestion JSONL
- `operator_review_queue.json` and `operator_review_queue.md` outputs for human and machine use

## Design guardrails
- stable IDs are derived from deterministic relationship anchors
- original ingestion/evidence records are not mutated
- provenance and governance references are carried through, not collapsed away
- secret-bearing fields are redacted before serialization
- queue items stay generic so future CRM, ERP, communications, or accounting connectors can reuse the same path
