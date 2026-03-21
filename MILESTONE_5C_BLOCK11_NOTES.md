# M5C Block 11 notes

This block adds target-group adapter package scaffolds and canonical request/response fixture packs.

## Added
- `src/start_here_extractor/target_group_adapter_packages.py`
- `scripts/build_target_group_adapter_packages.py`
- `scripts/build_canonical_request_response_fixture_packs.py`
- expanded `tests/test_milestone5c.py`
- README update

## Intent
Block 11 turns family-specific interface templates and canonical raw payload contracts into concrete target-group package scaffolds, then generates canonical request/response fixture packs for those scaffolds.

## Outputs
- `target_group_adapter_packages.json`
- `target_group_adapter_packages.md`
- `target_group_adapter_package_review_queue.json`
- `target_group_adapter_package_review_queue.md`
- `target_group_adapter_package_rollup.json`
- `target_group_adapter_package_rollup.md`
- `canonical_request_response_fixture_packs.json`
- `canonical_request_response_fixture_packs.md`
- `canonical_request_response_fixture_review_queue.json`
- `canonical_request_response_fixture_review_queue.md`
- `canonical_request_response_fixture_rollup.json`
- `canonical_request_response_fixture_rollup.md`

## Direction
This remains contract-driven and downstream-neutral. It does not mutate evidence, provenance, or execution journals. It sets up future concrete target packages and request/response fixtures for specific adapter families.
