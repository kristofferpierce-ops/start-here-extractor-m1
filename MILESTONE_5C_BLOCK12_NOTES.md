# M5C Block 12 notes

This block adds:

- `src/start_here_extractor/target_group_adapter_skeletons.py`
- `scripts/build_target_group_adapter_skeletons.py`
- `scripts/build_roundtrip_normalization_cases.py`
- round-trip normalization tests in `tests/test_milestone5c.py`
- README coverage for the new artifacts

It introduces:

- concrete target-group adapter skeletons derived from target-group adapter packages and canonical request/response fixture packs
- round-trip normalization cases that pair canonical request/response fixtures into deterministic request/response examples
- review queues and rollups for missing target-group skeleton routing or missing fixture pairs

New artifacts:

- `target_group_adapter_skeletons.json`
- `target_group_adapter_skeletons.md`
- `target_group_adapter_skeleton_review_queue.json`
- `target_group_adapter_skeleton_review_queue.md`
- `target_group_adapter_skeleton_rollup.json`
- `target_group_adapter_skeleton_rollup.md`
- `roundtrip_normalization_cases.json`
- `roundtrip_normalization_cases.md`
- `roundtrip_normalization_review_queue.json`
- `roundtrip_normalization_review_queue.md`
- `roundtrip_normalization_rollup.json`
- `roundtrip_normalization_rollup.md`

Design intent:

- keep target-group adapter logic contract-driven and target-neutral
- keep evidence immutable and provenance attached to upstream records rather than mutated into adapter state
- make request/response examples deterministic enough to support future live adapter implementations and round-trip normalization checks
