# Milestone 3E Closeout Block - `start_here_extractor`

This package extends the Milestone 3D extractor with **release hardening and CI closeout work**:

- no-secrets default CI on Windows, macOS, and Linux
- Windows sandbox **dry-run** smoke coverage in CI
- manual **workflow_dispatch** live-provider smoke workflow for:
  - Google Drive
  - Dropbox
  - Microsoft Graph / OneDrive
- local credential hygiene defaults via `.gitignore`
- release checklist and closeout notes

It preserves all Milestone 1 public interfaces, the Milestone 2 JSON inventory contract, and the additive Milestone 3 schema fields.

## What is new in Block E

- updated `.github/workflows/tests.yml`
- new `.github/workflows/live-smoke.yml`
- new `scripts/ci_sandbox_dry_run.py`
- new `.gitignore`
- new `MILESTONE_3E_CLOSEOUT_NOTES.md`
- new `MILESTONE_3_RELEASE_CHECKLIST.md`

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

## Local verification

```bash
python -m ruff check .
pytest
python scripts/validate_inventory.py examples/sample_inventory_extracted.jsonl
```

## CI policy in this block

The default CI workflow is **no-secrets** and should always be safe to run on:

- Windows
- macOS
- Linux

It covers:

- Ruff
- pytest
- schema validation
- Windows sandbox **dry-run** artifact generation only

The CI workflow does **not** run:
- real Windows Sandbox launches
- live cloud provider calls
- real AV engine calls

Those behaviors remain manual or workflow-dispatch only.

## Live cloud smoke workflow

This block adds a **manual** GitHub Actions workflow:

`.github/workflows/live-smoke.yml`

It is intended for controlled release checks and requires repository secrets:

- `GDRIVE_ACCESS_TOKEN`
- `DROPBOX_ACCESS_TOKEN`
- `GRAPH_ACCESS_TOKEN`

Only the selected provider needs a secret.

### Example local smoke mode

Google Drive:

```bash
python -m start_here_extractor.cli --cloud-provider gdrive --cloud-access-token <TOKEN> --cloud-query "drive_smoke_test" --output-dir out/remote_extracted --report-dir out/remote_reports
```

### Example GitHub live smoke run

Use **Actions → live-provider-smoke → Run workflow** and choose:

- `gdrive`
- `dropbox`
- or `graph`

with a query string that matches a known smoke ZIP in that provider.

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

## Scan and sandbox posture

Milestone 3D and 3E preserve the current scan/policy behavior:

- malicious AV or YARA match → `reject`
- scan engine execution failure → `warn` / `inconclusive`
- suspicious ZIP structure → `sandbox`
- Windows Sandbox support in CI is **dry-run artifact generation only**

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

## Credential hygiene

Do **not** commit these files:

- `credentials.json`
- `token.json`

This block adds a `.gitignore` entry for them by default.

Also avoid pasting live access tokens into terminals that are logged or into chat systems.

## Test suite

```bash
python -m ruff check .
pytest
python scripts/validate_inventory.py examples/sample_inventory_extracted.jsonl
```

## Safety posture

Milestone 3E does not weaken earlier protections.

- inspect first
- bounded single-member extraction
- Zip Slip defenses
- ZIP bomb limits
- strict ZIP validation
- policy-based sandbox escalation
- additive-only schema evolution


## Milestone 4A

This block begins a generic evidence-governance layer on top of the extractor:
- deterministic summary generation from inventory plus bounded preview only
- dangerous-instruction heuristics
- additive governance policy decisions
- append-only audit JSONL with audit refs
- retention status defaults

The existing `policy` field remains the operational extractor decision. The additive `policy_decision` field is a future-safe governance artifact designed to generalize later beyond ZIP files to other company evidence streams.


## Milestone 4B governance hardening

This stage adds future-safe governance hooks without narrowing the project into a telephony-only bridge. Cloud abuse acknowledgement is now gated behind an explicit operator approval reference when required, retention status is computed deterministically, audit JSONL streams can be resumed safely, and inventory records now carry a generic `governance` block designed to coexist later with jobs, invoices, labor, expenses, and purchasing evidence.


## Milestone 4C additions

- optional `--cloud-access-token-command` for runtime token resolution
- token health hints via `--cloud-token-expires-at` and `--cloud-token-min-valid-seconds`
- monitoring JSONL stream and `monitoring_ref` in inventory records
- governance review hooks for sandbox and cloud provider states
- no assumptions about the outer project root folder name


## Milestone 4D closeout

This release hardens governance and monitoring by removing raw cloud tokens from persisted records, preserving only non-secret token-health metadata, and adding a monitoring rollup helper for operational summaries.


## Milestone 5A: playbook engine, RBAC, and immutable action audit

This build adds a deterministic remediation playbook subsystem that keeps the existing extractor pipeline intact.

### New package entrypoint

```bash
start-here-playbook path/to/plan.json --workspace-root ./workspace --audit-dir ./out/audit --actor-id analyst-1 --role operator --dry-run
```

### Plan shape

A plan can be either a JSON list of actions or an object containing `plan_id` and `actions`.

Example:

```json
{
  "plan_id": "demo-plan",
  "actions": [
    {"id": "a1", "type": "write-file", "params": {"path": "notes/result.txt", "content": "hello"}},
    {"id": "a2", "type": "touch-marker", "params": {"path": "markers/complete.txt"}}
  ]
}
```

### Built-in actions
- `write-file`
- `delete-path`
- `touch-marker`

### Role defaults
- `viewer`: no playbook execution
- `analyst`: `playbook.run.dry_run`
- `operator`: `playbook.run`, `playbook.run.dry_run`
- `admin`: operator rights plus configure / override placeholders

All playbook actions are written to an append-only action audit stream with idempotency keys so reruns can safely skip already completed actions.

## Milestone 5C block 1: generalized ingestion backbone foundation

This stage starts the broader connector-first Milestone 5C direction by adding a generic ingestion journal on top of existing inventory artifacts.

What it adds:
- a connector-neutral ingestion record with `raw`, `normalized`, `matched`, `approved`, and `applied` pipeline stages
- deterministic `event_id` derivation from source identity and evidence fingerprints
- preserved provenance, governance refs, and review state without leaking secrets
- a journal builder script for turning inventory JSONL outputs into a reusable ingestion stream

Example:

```powershell
python .\scripts\build_ingestion_journal.py --inventory-dir .\out\reports --out-dir .\out\ingestion
```

This is intentionally additive. It does not replace the extractor inventory as source of truth. It creates the first generic backbone artifact that future connectors such as communications, CRM, and financial systems can share.


## Milestone 5C block 2: relationship memory and operator review queue scaffolding

This stage layers deterministic relationship-memory grouping and operator-review scaffolding on top of the generic ingestion journal.

It adds:
- a connector-neutral relationship memory snapshot built from ingestion records
- deterministic candidate entity IDs anchored to stable relationship keys
- a secret-safe operator review queue for records that still need match or approval decisions
- a builder script that writes machine-readable queue artifacts plus a human-readable markdown summary

Example:

```powershell
python .\scripts\build_relationship_memory.py --ingestion-path .\out\ingestion\ingestion-events.jsonl --out-dir .\out\relationship_memory
```


## Milestone 5C block 3: review decision application and matched/approved state transitions

This stage takes the operator review queue from Block 2 and adds the first deterministic review-application layer.

It adds:
- a secret-safe review decision journal
- matched and approved state transition scaffolding built from operator decisions
- a post-review relationship-memory and queue refresh
- machine-readable and markdown rollups for transition outcomes

Example:

```powershell
python .\scripts\apply_review_decisions.py --ingestion-path .\out\ingestion\ingestion-events.jsonl --queue-path .\out\relationship_memory\operator_review_queue.json --decisions-path .\out\review\review_decisions.json --out-dir .\out\review\applied --actor-id operator-1
```

This remains additive. The original ingestion stream is not mutated in place. Instead, the stage writes a derived state projection and a decision journal so future approval and application workflows can remain explainable and auditable.

## M5C Block 4 approved to applied scaffolding

The `scripts/apply_application_decisions.py` helper turns approved ingestion records into a generic application-routing step using an external target catalog and a decision file. It writes:

- `application_queue.json`
- `application_queue.md`
- `ingestion_state_applied_projection.jsonl`
- `application_decision_journal.jsonl`
- `application_transition_rollup.json`
- `application_transition_rollup.md`
- `application_queue_post_apply.json`
- `application_queue_post_apply.md`

This keeps downstream apply behavior connector-neutral while preserving provenance, approval history, and explainable operator routing decisions.

## M5C Block 5 adapter contract scaffolding

The `scripts/build_adapter_contracts.py` helper turns `applied` projection records into explicit adapter execution contracts using an external adapter catalog. It writes:

- `adapter_execution_contracts.json`
- `adapter_execution_contracts.md`
- `adapter_contract_review_queue.json`
- `adapter_contract_review_queue.md`
- `adapter_contract_rollup.json`
- `adapter_contract_rollup.md`

This keeps downstream execution contract-driven and future-safe. Real target executors can be added later without mutating evidence, provenance, or operator decision history.
