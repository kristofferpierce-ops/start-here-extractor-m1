# M5C Block 16 Notes

## Scope
Block 16 adds a promotion-readiness layer on top of dry-run harness result journals and replay outcome comparison packs. It also adds a live-integration candidate layer that stays offline and contract-driven while marking which target-group flows are clean enough to move into a future explicit live integration milestone.

## Added
- `src/start_here_extractor/target_group_adapter_promotion_readiness.py`
- `scripts/build_target_group_promotion_readiness_packs.py`
- `scripts/build_live_integration_candidate_packs.py`
- README update
- targeted tests in `tests/test_milestone5c.py`

## Outputs
- `target_group_promotion_readiness_packs.json`
- `target_group_promotion_readiness_packs.md`
- `target_group_promotion_readiness_review_queue.json`
- `target_group_promotion_readiness_review_queue.md`
- `target_group_promotion_readiness_rollup.json`
- `target_group_promotion_readiness_rollup.md`
- `live_integration_candidate_packs.json`
- `live_integration_candidate_packs.md`
- `live_integration_candidate_review_queue.json`
- `live_integration_candidate_review_queue.md`
- `live_integration_candidate_rollup.json`
- `live_integration_candidate_rollup.md`

## Design notes
- promotion readiness is derived from replay comparison cleanliness, not live execution
- live integration candidates remain explicitly non-live and require future manual enablement
- no raw evidence is mutated and provenance remains attached through the derived artifacts
