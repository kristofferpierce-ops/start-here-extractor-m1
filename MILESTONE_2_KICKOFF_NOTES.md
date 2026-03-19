# Milestone 2 Kickoff Notes

This package implements the Milestone 2 kickoff scope from the uploaded Milestone 2 PDF.

## Included deliverables

- `src/start_here_extractor/jsonl.py`
- `src/start_here_extractor/batch.py`
- `src/start_here_extractor/cloud/base.py`
- `src/start_here_extractor/cloud/gdrive_stub.py`
- `src/start_here_extractor/cloud/graph_stub.py`
- `src/start_here_extractor/cloud/dropbox_stub.py`
- `tests/test_jsonl.py`
- `tests/test_batch_ordering.py`
- `tests/test_cloud_stubs.py`
- CLI support for:
  - `--all`
  - `--jsonl-out`
  - `--fail-fast`

## Preserved behaviors

- existing Milestone 1 single-run and per-ZIP workflows still work
- inventory schema contract remains stable
- batch mode writes the same record shape line-by-line
- no network activity is introduced by the cloud stub layer

## Important implementation choice

`process_zip()` now records corrupt ZIP failures as per-ZIP error records instead of allowing a bad archive to crash a batch. This is necessary for the Milestone 2 requirement that one bad ZIP not ruin the batch.
