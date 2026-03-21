# M5C Block 13 Notes

This block adds target-group adapter implementation shells and end-to-end round-trip fixture execution packs.

## Added
- `src/start_here_extractor/target_group_adapter_implementation_shells.py`
- `scripts/build_target_group_adapter_implementation_shells.py`
- `scripts/build_end_to_end_roundtrip_fixture_execution_packs.py`

## Purpose
- turn target-group adapter skeletons into concrete implementation shell scaffolds
- aggregate round-trip normalization cases into executable end-to-end fixture packs
- keep routing catalog-driven and target-neutral
- preserve provenance and avoid mutating raw evidence
