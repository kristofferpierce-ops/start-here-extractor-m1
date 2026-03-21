# M5C Block 9 notes

This block adds target-family runner stubs and normalized collector fixtures on top of the Block 8 runner-interface contract layer.

## Added

- `src/start_here_extractor/target_runner_families.py`
- `scripts/build_target_family_runner_stubs.py`
- `scripts/build_target_family_collector_fixtures.py`
- README update
- expanded `tests/test_milestone5c.py`

## Outputs

- `target_family_runner_stubs.json`
- `target_family_runner_stubs.md`
- `target_family_runner_review_queue.json`
- `target_family_runner_review_queue.md`
- `target_family_runner_rollup.json`
- `target_family_runner_rollup.md`
- `target_family_collector_fixtures.json`
- `target_family_collector_fixtures.md`
- `target_family_collector_fixture_review_queue.json`
- `target_family_collector_fixture_review_queue.md`
- `target_family_collector_fixture_rollup.json`
- `target_family_collector_fixture_rollup.md`

## Intent

Keep the system target-neutral while giving future adapter families explicit runner stub templates and canonical collector fixtures. This stays separate from raw evidence and preserves deterministic provenance-aware state transitions.
