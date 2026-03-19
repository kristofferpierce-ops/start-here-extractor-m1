# Milestone 3B Block - `start_here_extractor`

This package extends the Milestone 3A extractor with the Windows Sandbox orchestration block:

- strict ZIP hardening with central-directory vs local-header reconciliation
- additive policy decisions: `allow`, `warn`, `sandbox`, `reject`
- retry/backoff utilities with `Retry-After` support for future provider integrations
- single-writer JSONL output with optional `fsync` durability
- Windows Sandbox Runner v1 with hardened `.wsb` generation, staging/results folder mapping, completion sentinel handling, and dry-run mode
- additive inventory schema blocks for `run`, `provenance`, `zip_hardening`, `policy`, `sandbox`, and `batch`

Milestone 1 public interfaces and the Milestone 2 JSON contract remain intact:

- single-ZIP and per-ZIP runs still work
- batch mode still writes one JSON object per line with no wrapper record types
- the original compatibility fields remain present
- the same inspect-first, extract-minimally safety posture remains in place

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

So these all work equally well:

- `start_here_extractor_m3_block_a`
- `start_here_extractor`
- `my_zip_tool`

## Install

```bash
cd <your-project-root>
python -m pip install -e .
```

For local development tools:

```bash
python -m pip install -e .[dev]
```

## Basic single-run usage

Process a single ZIP and write one per-ZIP inventory file:

```bash
python -m start_here_extractor.cli sample.zip --output-dir out/extracted --report-dir out/reports
```

Process discovered ZIPs under a root in the original Milestone 1 style:

```bash
python -m start_here_extractor.cli --root incoming_zips --output-dir out/extracted --report-dir out/reports
```

## Batch mode

Batch mode remains additive and opt-in.

```bash
python -m start_here_extractor.cli --all --root incoming_zips --output-dir out/extracted --report-dir out/reports
```

Use a specific shared JSONL output path:

```bash
python -m start_here_extractor.cli --all --root incoming_zips --output-dir out/extracted --report-dir out/reports --jsonl-out out/reports/inventories.jsonl
```

Stop after the first ZIP with recorded errors:

```bash
python -m start_here_extractor.cli --all --root incoming_zips --output-dir out/extracted --report-dir out/reports --fail-fast
```

Force per-line durability in batch JSONL mode:

```bash
python -m start_here_extractor.cli --all --root incoming_zips --output-dir out/extracted --report-dir out/reports --jsonl-out out/reports/inventories.jsonl --durable-jsonl
```

Disable strict ZIP hardening if you are doing compatibility triage and want to compare behavior:

```bash
python -m start_here_extractor.cli sample.zip --output-dir out/extracted --report-dir out/reports --no-strict-zip-validation
```

### Batch mode guarantees

- output file is UTF-8 JSON Lines with `\n` line endings and no BOM
- each ZIP produces exactly one JSON record line
- records are appended one at a time by a single writer
- discovery order is normalized by deterministic sorted path order in batch mode
- one bad ZIP does not stop the batch unless `--fail-fast` is set
- optional `--durable-jsonl` flushes and `fsync`s each line for stronger crash durability

## Windows Sandbox block (Milestone 3B)

Sandbox support is additive and opt-in.

Generate hardened Windows Sandbox artifacts without launching the sandbox:

```bash
python -m start_here_extractor.cli suspicious.zip --output-dir out/extracted --report-dir out/reports --sandbox-platform windows-sandbox --sandbox-dry-run
```

Common sandbox flags:

- `--sandbox-platform windows-sandbox`
- `--sandbox-dry-run`
- `--sandbox-timeout-seconds 120`
- `--sandbox-root out/sandbox`
- `--sandbox-command "Write-Host 'hello from sandbox'"`
- `--sandbox-enable-network`
- `--sandbox-enable-clipboard`
- `--sandbox-enable-vgpu`

Default hardened Windows Sandbox settings in this block:

- networking disabled
- clipboard redirection disabled
- vGPU disabled
- staging folder mapped read-only
- results folder mapped writable
- `LogonCommand` points to a pre-staged PowerShell job script

This block focuses on orchestration and dry-run validation. It does **not** claim full in-sandbox extraction and scanning yet.

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

These are additive only:

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

## Cloud locator scaffolding

The Milestone 2 provider stubs remain under `src/start_here_extractor/cloud/`.

This Milestone 3A block does **not** turn them into live network integrations yet. It only adds the lower-level reliability and policy pieces they will use later.

## New internal modules in this block

- `src/start_here_extractor/sandbox/base.py`
- `src/start_here_extractor/sandbox/windows.py`
- `src/start_here_extractor/zip_hardening/strict_validator.py`
- `src/start_here_extractor/policy.py`
- `src/start_here_extractor/net/retry.py`
- `src/start_here_extractor/io/jsonl_writer.py`

## PowerShell helper

The parity helper remains at `scripts/start_here_helper.ps1`.

Examples:

```powershell
./scripts/start_here_helper.ps1 -ZipPath .\sample.zip -Mode Inspect
./scripts/start_here_helper.ps1 -ZipPath .\sample.zip -Mode Extract -OutputDir .\out
```

The PowerShell helper is still focused on inspect/extract parity. It does not replace the Python batch JSONL pipeline.

## Test suite

Run the full suite:

```bash
ruff check .
pytest
python scripts/validate_inventory.py examples/sample_inventory_extracted.jsonl
```

Milestone 3B adds tests for:

- central-directory vs local-header mismatch detection
- data descriptor ambiguity flags
- duplicate name detection
- retry/backoff honoring `Retry-After`
- durable JSONL writer behavior
- project-root-folder-name independence
- hardened `.wsb` XML generation
- sandbox dry-run artifact emission
- sandbox policy + processor integration for suspicious ZIPs

## Safety posture

Milestone 3B does not weaken earlier protections.

- inspect first
- bounded single-member extraction only
- Zip Slip protections remain enforced
- ZIP bomb size and ratio limits remain enforced
- strict ZIP hardening is additive, not a replacement for the original limits
- AV hooks remain advisory telemetry, not a primary gate
