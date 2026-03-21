# M5C Block 15 Notes

This block adds two new contract-driven layers on top of the replayable dry-run orchestration packs:

- dry-run harness result journals
- replay outcome comparison packs

## Goals

- keep all execution offline and replayable
- journal harness results separately from evidence
- compare replay outcomes against expected fixture outputs
- preserve provenance-safe, deterministic identifiers

## New scripts

- `scripts/build_dry_run_harness_result_journals.py`
- `scripts/build_replay_outcome_comparison_packs.py`

## New module

- `src/start_here_extractor/target_group_adapter_harness_results.py`
