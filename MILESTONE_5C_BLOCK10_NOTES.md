# M5C Block 10 notes

This block adds family-specific adapter interface templates and canonical raw payload contracts.

## Added
- `src/start_here_extractor/family_interface_templates.py`
- `scripts/build_family_interface_templates.py`
- `scripts/build_canonical_raw_payload_contracts.py`
- expanded `tests/test_milestone5c.py`

## Outputs
- `family_interface_templates.json`
- `family_interface_templates.md`
- `family_interface_template_review_queue.json`
- `family_interface_template_review_queue.md`
- `family_interface_template_rollup.json`
- `family_interface_template_rollup.md`
- `canonical_raw_payload_contracts.json`
- `canonical_raw_payload_contracts.md`
- `canonical_raw_payload_review_queue.json`
- `canonical_raw_payload_review_queue.md`
- `canonical_raw_payload_rollup.json`
- `canonical_raw_payload_rollup.md`

## Intent
Block 10 adds family-specific template contracts on top of Block 9 target-family runner stubs so future concrete adapters can share canonical raw payload rules without changing evidence, provenance, or execution journaling.
