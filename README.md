# Milestone 3C Block - `start_here_extractor`

This package extends the Milestone 3B extractor with **real cloud locator implementations** for:

- Google Drive
- Dropbox
- Microsoft Graph / OneDrive

It preserves the Milestone 1 public interfaces, the Milestone 2 JSON inventory contract, and the additive Milestone 3A/3B schema fields.

## What is new in Block C

- real provider modules under `src/start_here_extractor/cloud/`
- provider-specific auth config dataclasses
- remote search/list paging support
- provider-aware download methods using atomic temp-file writes
- retry/backoff integration for provider requests
- optional CLI remote smoke mode using `--cloud-provider`
- mocked tests for paging, throttling, and download behavior

## Important root-folder note

The **outer project folder name is not hardcoded**.

You can rename the extracted project root folder to whatever you want, as long as the internal structure stays the same:

- `.github/`
- `examples/`
- `schemas/`
- `scripts/`
- `src/`
- `tests/`
- `pyproject.toml`

## Install

```bash
cd <your-project-root>
python -m pip install -e .
python -m pip install -e .[dev]
```

## Local ZIP usage

Single ZIP:

```bash
python -m start_here_extractor.cli sample.zip --output-dir out/extracted --report-dir out/reports
```

Batch mode:

```bash
python -m start_here_extractor.cli --all --root incoming_zips --output-dir out/extracted --report-dir out/reports --jsonl-out out/reports/inventories.jsonl --durable-jsonl
```

## Remote cloud smoke mode

Remote mode is additive and opt-in.

General pattern:

```bash
python -m start_here_extractor.cli --cloud-provider <gdrive|dropbox|graph> --cloud-access-token <TOKEN> --cloud-query "start here" --output-dir out/extracted --report-dir out/reports
```

Process all found remote ZIPs instead of only the first result:

```bash
python -m start_here_extractor.cli --all --cloud-provider dropbox --cloud-access-token <TOKEN> --cloud-query "start here" --output-dir out/extracted --report-dir out/reports --jsonl-out out/reports/inventories.jsonl
```

Useful provider-specific flags:

- Google Drive
  - `--cloud-drive-id <ID>`
  - `--cloud-acknowledge-abuse`
- Microsoft Graph
  - `--graph-drive-scope me/drive/root`
- Any provider
  - `--cloud-folder-id <ID_OR_PATH>`
  - `--cloud-page-size 100`
  - `--cloud-max-pages 10`
  - `--cloud-download-dir out/downloads`

## Windows Sandbox block

Sandbox support remains additive and opt-in.

Dry-run generation:

```bash
python -m start_here_extractor.cli suspicious.zip --output-dir out/extracted --report-dir out/reports --sandbox-platform windows-sandbox --sandbox-dry-run --sandbox-root out/sandbox
```

## Inventory output

### Stable compatibility fields

These remain available for Milestone 1 and Milestone 2 consumers:

- `zip_path`
- `start_here`
- `size_bytes`
- `md5`
- `encoding`
- `preview_text`
- `scan`
- `errors`
- `warnings`

### Additive Milestone 3 fields

- `run`
- `provenance`
- `zip_hardening`
- `policy`
- `sandbox`
- `batch`
- `text_summary`
- `match`
- `extraction`

Validate JSONL against the packaged schema:

```bash
python scripts/validate_inventory.py examples/sample_inventory_extracted.jsonl
```

## Cloud modules in this block

- `src/start_here_extractor/cloud/http.py`
- `src/start_here_extractor/cloud/runtime.py`
- `src/start_here_extractor/cloud/gdrive.py`
- `src/start_here_extractor/cloud/dropbox.py`
- `src/start_here_extractor/cloud/graph.py`

The earlier Milestone 2 stubs are still present for compatibility and comparison.

## Test suite

```bash
ruff check .
pytest
python scripts/validate_inventory.py examples/sample_inventory_extracted.jsonl
```

Milestone 3C adds mocked tests for:

- Google Drive paging and download
- Dropbox throttling / `Retry-After` handling and download
- Microsoft Graph paging and content download
- root-folder-name independence for remote downloads

## Safety posture

Milestone 3C does not weaken earlier protections.

- inspect first
- bounded single-member extraction only
- Zip Slip protections remain enforced
- ZIP bomb size and ratio limits remain enforced
- strict ZIP hardening remains additive
- AV hooks remain advisory telemetry, not a primary gate
- remote downloads stage to local temp files with atomic replacement


## Milestone 3D scan integration

This build adds pluggable AV and optional YARA scanning without changing the outer project root assumptions.

New CLI flags:
- `--av-command` with `--av-engine {generic,clamav,defender}`
- `--scan-timeout-seconds`
- `--yara-command`
- `--yara-rules`
- `--yara-ruleset-id`
- `--yara-compiled-rules` plus `--yara-allow-compiled-rules`

Examples:

```powershell
python -m start_here_extractor.cli .\examples\sample_success.zip --output-dir .\out\scan_out --report-dir .\out\scan_reports --av-engine clamav --av-command "clamscan --no-summary {path}"
```

```powershell
python -m start_here_extractor.cli .\examples\sample_success.zip --output-dir .\out\scan_out --report-dir .\out\scan_reports --yara-command "yara {compiled_flag} {rules} {path}" --yara-rules .\rules\sample.yar --yara-ruleset-id sample-rules
```
