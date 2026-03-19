# Milestone 3B Block Notes

This package extends Milestone 3A with the first sandbox orchestration block:

- `SandboxRunner` abstraction
- `WindowsSandboxRunner` v1
- hardened `.wsb` generation
- mapped staging/results folders with read-only vs writable permissions
- `LogonCommand` generation for a single sandbox job script
- completion sentinel path support
- timeout-aware runtime path for real Windows hosts
- dry-run mode that emits sandbox config and command artifacts without launching Windows Sandbox
- additive CLI flags for sandbox configuration
- additive inventory fields inside the existing `sandbox` block

## Important scope note

This block focuses on **orchestration and auditability**, not a full in-sandbox extraction pipeline yet.

What is included:
- sandbox config generation
- job script generation
- host staging/results directory preparation
- dry-run verification path
- optional Windows host launch path with sentinel waiting and timeout handling

What is intentionally not claimed yet:
- full in-sandbox extraction execution parity
- live CI execution of Windows Sandbox
- AV or YARA gating inside the sandbox
- Linux/macOS runner implementations

## Root folder independence

The outer project root folder name is still not hardcoded.

## Validation completed for this block

- `ruff check .`
- `pytest`
- `python scripts/validate_inventory.py examples/sample_inventory_extracted.jsonl`

## Suggested smoke test

```bash
python -m start_here_extractor.cli suspicious.zip \
  --output-dir out/extracted \
  --report-dir out/reports \
  --sandbox-platform windows-sandbox \
  --sandbox-dry-run \
  --sandbox-root out/sandbox
```

That should produce an inventory record with:
- `policy.decision == "sandbox"` for suspicious ZIPs
- `sandbox.enabled == true`
- emitted `.wsb` and `run_job.ps1` artifacts under the sandbox root
