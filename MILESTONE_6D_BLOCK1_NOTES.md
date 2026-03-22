# Milestone 6D Block 1 Notes

This block starts M6D by turning lineage/replay readiness into explicit source replay plan packs.

## What it adds
- `src/start_here_extractor/source_replay_plans.py`
- `scripts/build_source_replay_plan_packs.py`
- targeted `tests/test_milestone6.py` coverage for the new planning layer
- README coverage for the new Milestone 6D step

## Outputs
- `source_replay_plan_packs.json`
- `source_replay_plan_review_queue.json`
- `source_replay_plan_rollup.json`

## Why this comes next
M6C stops at the question of whether a source is safe to replay. The next deterministic layer is to materialize explicit replay plans for sources that are ready, protected, or blocked.

This block keeps the system offline and provenance-safe while:
- translating readiness state into replay mode
- preserving idempotency keys and durable lineage references
- distinguishing compare-only replay from resume-from-approved replay and full replay
- surfacing blocked sources in a dedicated review queue instead of silently planning them

## Design guardrails
- no live downstream writes
- no mutation of raw evidence or durable lineage records
- replay plans remain derived artifacts only
- protected replay states stay compare-first and write-constrained
