# Milestone 1 traceability map

## Core requirement to implementation

- Inspect-first ZIP handling -> `src/start_here_extractor/inspector.py`
- Deterministic START HERE matching -> `src/start_here_extractor/matcher.py`
- Zip Slip defenses -> `src/start_here_extractor/utils.py`, `src/start_here_extractor/extractor.py`
- ZIP bomb/resource caps -> `src/start_here_extractor/inspector.py`, `src/start_here_extractor/extractor.py`
- Bounded preview with UTF-16 fallback -> `src/start_here_extractor/reader.py`
- Advisory AV telemetry -> `src/start_here_extractor/av.py`
- JSONL inventory output -> `src/start_here_extractor/reporter.py`, `schemas/inventory.schema.json`
- CLI orchestration -> `src/start_here_extractor/cli.py`
- Acceptance tests -> `tests/test_milestone1.py`
- PowerShell helper -> `scripts/start_here_helper.ps1`
- Packaging + CI -> `pyproject.toml`, `.github/workflows/tests.yml`
- Schema validation in CI -> `scripts/validate_inventory.py`, `.github/workflows/tests.yml`
- Final signoff artifact -> `MILESTONE_1_SIGNOFF_CHECKLIST.md`

## Acceptance coverage

- T1 case-insensitive match -> `test_t1_case_insensitive_found`
- T2 prefer `.txt` over `.md` -> `test_t2_prefer_txt_over_md`
- T3 ambiguity error mode -> `test_t3_error_on_multiple_when_policy_error`
- T4 Zip Slip rejection -> `test_t4_zip_slip_rejected`
- T5 declared size cap -> `test_t5_declared_size_over_cap`
- T6 compression ratio cap -> `test_t6_ratio_over_cap`
- T7 UTF-16 readable preview -> `test_t7_utf16_preview_readable`

## Additional explicit hardening coverage

- Absolute path rejection (`/` and Windows drive style) -> `test_absolute_path_rejected`
- Inventory still emitted on no-match -> `test_no_match_still_emits_inventory`
- Non-ASCII CP437 filename handling -> `test_cp437_non_ascii_directory_name_decodes_cleanly`
- Every generated inventory validates against schema -> `load_inventory()` helper inside `tests/test_milestone1.py`
