# Milestone 3A Block Notes

This package implements the first Milestone 3 block on top of the cleaned Milestone 2 kickoff build.

Included in this block:

- strict ZIP hardening with central-directory vs local-header reconciliation
- additive policy decisions (`allow`, `warn`, `sandbox`, `reject`)
- retry/backoff utilities with `Retry-After` support
- single-writer JSONL writer with optional `fsync` durability
- additive schema update for `run`, `provenance`, `zip_hardening`, `policy`, `sandbox`, and `batch`
- explicit note and test coverage that the **outer project root folder name can be changed** without breaking runtime behavior

Not included yet:

- Windows Sandbox runner
- live Google Drive / Dropbox / Microsoft Graph connectors
- real AV + YARA gating
- mocked cloud paging / throttling integration tests

Validation completed in this environment:

- `ruff check .` → passed
- `pytest` → passed
- `python scripts/validate_inventory.py examples/sample_inventory_extracted.jsonl` → passed
