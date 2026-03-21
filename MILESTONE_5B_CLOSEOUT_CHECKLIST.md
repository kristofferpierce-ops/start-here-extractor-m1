# Milestone 5B closeout checklist

Use this checklist before treating Milestone 5B as merge-ready or mainline-ready.

## Core implementation checkpoints

- [ ] Refresh-capable cloud token runtime is present and tested.
- [ ] Provider health, quota, and retry telemetry are present and secret-safe.
- [ ] Hosted live-smoke summary generation is present and uploads artifacts even when smoke fails.
- [ ] Live-smoke artifact contracts are versioned and validated.
- [ ] Provider-matrix smoke gating is present for gdrive, dropbox, and graph.
- [ ] Release-gate artifacts and operator runbook are present.
- [ ] Mainline-readiness artifacts and normalized release bundle are present.

## Validation checkpoints

- [ ] `python -m pytest .\tests\test_milestone5b.py -q`
- [ ] `python -m pytest -q`
- [ ] `python -m ruff check .`
- [ ] `python -m start_here_extractor.cli --help`
- [ ] `python -m start_here_extractor.playbooks_cli --help`
- [ ] `python .\scripts\live_smoke_summary.py --help`
- [ ] `python .\scripts\live_smoke_matrix.py --help`
- [ ] `python .\scripts\live_smoke_release_gate.py --help`
- [ ] `python .\scripts\live_smoke_mainline_readiness.py --help`

## Hosted smoke promotion rules

- [ ] Required providers pass the matrix gate.
- [ ] No invalid artifact contracts are present.
- [ ] No unexpected provider artifacts are present.
- [ ] The operator runbook is checked in and available in the release artifacts.
- [ ] The closeout checklist is checked in and available in the release artifacts.
- [ ] `live_smoke_release_gate.json` says `promote=true` before merge readiness is claimed.
- [ ] `live_smoke_mainline_readiness.json` says `mainline_ready=true` before a main-branch promotion is treated as complete.
- [ ] Main-branch workflow runs use the required acknowledgement string before promotion is treated as valid.

## Operator review checkpoints

- [ ] No raw token material appears in smoke summaries, matrix artifacts, release-gate artifacts, runbooks, or release bundles.
- [ ] Optional-provider failures are documented and intentionally reviewed before mainline promotion.
- [ ] The normalized release bundle reflects the same provider set, decisions, and artifact versions as the source artifacts.
