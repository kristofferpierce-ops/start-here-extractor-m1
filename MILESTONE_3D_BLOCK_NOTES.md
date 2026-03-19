# Milestone 3D Block Notes

This block implements the AV + optional YARA plugin contract and policy-driven scan gating described in the Milestone 3 kickoff plan.

## New behavior
- Adds a scan integration layer that preserves the existing inventory contract and extends the `scan` block additively.
- Supports command-based AV scanning with engine hints for:
  - `generic`
  - `clamav`
  - `defender`
- Supports optional command-based YARA scanning with:
  - rules path
  - ruleset identifier
  - explicit acknowledgement for compiled rules
- Uses scan results to affect policy outcomes:
  - malicious AV result -> reject
  - YARA match -> reject
  - blocked or errored scan -> warn
- Keeps the outer project root folder rename-safe with no hardcoded root-name assumptions.

## Updated files
- `src/start_here_extractor/scan.py`
- `src/start_here_extractor/av.py`
- `src/start_here_extractor/policy.py`
- `src/start_here_extractor/processor.py`
- `src/start_here_extractor/types.py`
- `src/start_here_extractor/reporter.py`
- `src/start_here_extractor/cli.py`
- `schemas/inventory.schema.json`
- `README.md`
- `pyproject.toml`

## New tests
- `tests/test_milestone3d.py`

## Validation
- `python -m ruff check .`
- `pytest`
- `python scripts/validate_inventory.py examples/sample_inventory_extracted.jsonl`

## Version
- package version bumped to `0.6.0`
