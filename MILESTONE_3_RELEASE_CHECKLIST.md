# Milestone 3 Release Checklist

## Local verification
- [ ] `python -m pip install -e .[dev]`
- [ ] `python -m ruff check .`
- [ ] `pytest`
- [ ] `python scripts/validate_inventory.py examples/sample_inventory_extracted.jsonl`

## Manual local smoke tests
- [ ] local single-ZIP extraction passes
- [ ] batch JSONL output passes
- [ ] strict ZIP mismatch triggers `sandbox` policy in dry-run mode
- [ ] Google Drive live smoke test passes
- [ ] AV missing-binary path yields `warn` / `scan-inconclusive`
- [ ] YARA missing-binary path yields `warn` / `scan-inconclusive`

## GitHub workflow verification
- [ ] `tests.yml` green on Windows
- [ ] `tests.yml` green on macOS
- [ ] `tests.yml` green on Linux
- [ ] Windows CI sandbox dry-run step passes
- [ ] manual `live-provider-smoke` workflow verified for at least one provider

## Secret hygiene
- [ ] `credentials.json` not committed
- [ ] `token.json` not committed
- [ ] live provider tokens stored only in repo secrets for GitHub workflows
- [ ] previously exposed tokens rotated

## Release closeout
- [ ] commit and push final Milestone 3 state
- [ ] create annotated tag for Milestone 3 closeout
- [ ] publish release notes / archive
