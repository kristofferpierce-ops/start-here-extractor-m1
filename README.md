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

## M5C Block 6 adapter execution journaling and outcome ingestion

The `scripts/apply_adapter_execution_outcomes.py` helper takes planned adapter contracts plus a decision file and turns them into deterministic execution outcomes. It writes:

- `ingestion_state_execution_projection.jsonl`
- `adapter_execution_journal.jsonl`
- `adapter_execution_journal.md`
- `adapter_execution_contracts_post_execute.json`
- `adapter_execution_contracts_post_execute.md`
- `adapter_execution_rollup.json`
- `adapter_execution_rollup.md`

This keeps execution explainable and future-safe. Adapter outcomes are journaled separately, projected back into derived ingestion state, and can mark follow-up review without mutating raw evidence or provenance.

## M5C Block 7 adapter runner stubs and external outcome collector scaffolding

The `scripts/build_adapter_runner_jobs.py` helper turns runnable adapter contracts into dispatchable runner-job envelopes using an external runner catalog. It writes:

- `adapter_runner_jobs.json`
- `adapter_runner_jobs.md`
- `adapter_runner_review_queue.json`
- `adapter_runner_review_queue.md`
- `adapter_runner_rollup.json`
- `adapter_runner_rollup.md`

The companion `scripts/collect_adapter_execution_outcomes.py` helper turns external runner payloads into normalized adapter execution decisions that can feed the Block 6 execution-ingestion step. It writes:

- `collected_adapter_execution_decisions.json`
- `collected_adapter_execution_decisions.md`
- `external_outcome_review_queue.json`
- `external_outcome_review_queue.md`
- `external_outcome_rollup.json`
- `external_outcome_rollup.md`

This keeps execution target-neutral while adding a clean bridge from planned contracts to runnable jobs and then back from external outcomes into deterministic internal decisions.

## M5C Block 8 runner interfaces and collector normalization contracts

The `scripts/build_runner_interface_contracts.py` helper turns adapter runner jobs into stable runner-interface contracts using an external interface catalog. It writes:

- `adapter_runner_interface_contracts.json`
- `adapter_runner_interface_contracts.md`
- `adapter_runner_interface_review_queue.json`
- `adapter_runner_interface_review_queue.md`
- `adapter_runner_interface_rollup.json`
- `adapter_runner_interface_rollup.md`

The `scripts/normalize_external_runner_outcomes.py` helper takes raw external runner payloads plus those interface contracts and normalizes them into one canonical collector shape. It writes:

- `normalized_external_runner_outcomes.json`
- `normalized_external_runner_outcomes.md`
- `collector_normalization_review_queue.json`
- `collector_normalization_review_queue.md`
- `collector_normalization_rollup.json`
- `collector_normalization_rollup.md`

This creates a stable seam for future real runner adapters and downstream-specific result formats without changing the execution journal or evidence model.

## M5C Block 9 target-family runner stubs and collector fixtures

The `scripts/build_target_family_runner_stubs.py` helper turns runner-interface contracts into concrete target-family runner stubs using a target-family catalog. It writes:

- `target_family_runner_stubs.json`
- `target_family_runner_stubs.md`
- `target_family_runner_review_queue.json`
- `target_family_runner_review_queue.md`
- `target_family_runner_rollup.json`
- `target_family_runner_rollup.md`

The companion `scripts/build_target_family_collector_fixtures.py` helper turns those target-family runner stubs into normalized collector fixtures for success, failure, defer, and skip flows. It writes:

- `target_family_collector_fixtures.json`
- `target_family_collector_fixtures.md`
- `target_family_collector_fixture_review_queue.json`
- `target_family_collector_fixture_review_queue.md`
- `target_family_collector_fixture_rollup.json`
- `target_family_collector_fixture_rollup.md`

This creates concrete target-family scaffolding for future real adapters while keeping execution contract-driven, collector-friendly, and provenance-safe.


## M5C Block 10 family-specific adapter interface templates and canonical raw payload contracts

The `scripts/build_family_interface_templates.py` helper turns target-family runner stubs into family-specific adapter interface templates using an external template catalog. It writes:

- `family_interface_templates.json`
- `family_interface_templates.md`
- `family_interface_template_review_queue.json`
- `family_interface_template_review_queue.md`
- `family_interface_template_rollup.json`
- `family_interface_template_rollup.md`

The companion `scripts/build_canonical_raw_payload_contracts.py` helper turns those templates into canonical raw payload contracts for target groups. It writes:

- `canonical_raw_payload_contracts.json`
- `canonical_raw_payload_contracts.md`
- `canonical_raw_payload_review_queue.json`
- `canonical_raw_payload_review_queue.md`
- `canonical_raw_payload_rollup.json`
- `canonical_raw_payload_rollup.md`

## M5C Block 11 target-group adapter package scaffolds and canonical request/response fixture packs

The `scripts/build_target_group_adapter_packages.py` helper turns family interface templates and canonical raw payload contracts into target-group adapter package scaffolds using a target-group catalog. It writes:

- `target_group_adapter_packages.json`
- `target_group_adapter_packages.md`
- `target_group_adapter_package_review_queue.json`
- `target_group_adapter_package_review_queue.md`
- `target_group_adapter_package_rollup.json`
- `target_group_adapter_package_rollup.md`

The companion `scripts/build_canonical_request_response_fixture_packs.py` helper turns those package scaffolds into canonical request/response fixture packs. It writes:

- `canonical_request_response_fixture_packs.json`
- `canonical_request_response_fixture_packs.md`
- `canonical_request_response_fixture_review_queue.json`
- `canonical_request_response_fixture_review_queue.md`
- `canonical_request_response_fixture_rollup.json`
- `canonical_request_response_fixture_rollup.md`

This creates a stable family-specific seam for future concrete adapters and payload collectors while keeping the pipeline contract-driven, provenance-safe, and downstream-neutral.

## M5C Block 12 target-group adapter skeletons and round-trip normalization cases

The `scripts/build_target_group_adapter_skeletons.py` helper turns target-group adapter packages and canonical request/response fixture packs into concrete target-group adapter skeletons using a target-group skeleton catalog. It writes:

- `target_group_adapter_skeletons.json`
- `target_group_adapter_skeletons.md`
- `target_group_adapter_skeleton_review_queue.json`
- `target_group_adapter_skeleton_review_queue.md`
- `target_group_adapter_skeleton_rollup.json`
- `target_group_adapter_skeleton_rollup.md`

The companion `scripts/build_roundtrip_normalization_cases.py` helper turns those skeletons plus the request/response fixture packs into round-trip normalization cases. It writes:

- `roundtrip_normalization_cases.json`
- `roundtrip_normalization_cases.md`
- `roundtrip_normalization_review_queue.json`
- `roundtrip_normalization_review_queue.md`
- `roundtrip_normalization_rollup.json`
- `roundtrip_normalization_rollup.md`

This creates a concrete target-group adapter seam for future request/response implementations while keeping the pipeline contract-driven, provenance-safe, and downstream-neutral.


## M5C Block 13

Block 13 adds target-group adapter implementation shells and end-to-end round-trip fixture execution packs. These remain contract-driven and target-neutral, preserving provenance while preparing for concrete adapter implementations in later blocks.

## Milestone 5C Block 14

Block 14 adds replayable dry-run execution harnesses and orchestration packs on top of the target-group adapter implementation shells. It keeps execution offline and contract-driven while making the implementation shells runnable against the end-to-end fixture packs.

### New scripts
- `scripts/build_target_group_adapter_execution_harnesses.py`
- `scripts/build_replayable_dry_run_orchestration_packs.py`

### New artifacts
- `target_group_adapter_execution_harnesses.json`
- `target_group_adapter_execution_harness_review_queue.json`
- `target_group_adapter_execution_harness_rollup.json`
- `replayable_dry_run_orchestration_packs.json`
- `replayable_dry_run_orchestration_review_queue.json`
- `replayable_dry_run_orchestration_rollup.json`


## M5C Block 15

Block 15 adds dry-run harness result journals and replay outcome comparison packs on top of the replayable dry-run orchestration layer. It keeps execution offline and contract-driven while producing auditable result journals and comparison artifacts for replay outcomes.

### New scripts
- `scripts/build_dry_run_harness_result_journals.py`
- `scripts/build_replay_outcome_comparison_packs.py`

### New artifacts
- `dry_run_harness_result_journals.json`
- `dry_run_harness_result_review_queue.json`
- `dry_run_harness_result_rollup.json`
- `replay_outcome_comparison_packs.json`
- `replay_outcome_comparison_review_queue.json`
- `replay_outcome_comparison_rollup.json`


## M5C Block 16

Block 16 adds target-group promotion readiness packs and live integration candidate packs on top of the dry-run harness result and replay comparison layer. It keeps everything offline and contract-driven while marking which target-group flows are clean enough to move into a future explicit live integration milestone.

### New scripts
- `scripts/build_target_group_promotion_readiness_packs.py`
- `scripts/build_live_integration_candidate_packs.py`

### New artifacts
- `target_group_promotion_readiness_packs.json`
- `target_group_promotion_readiness_review_queue.json`
- `target_group_promotion_readiness_rollup.json`
- `live_integration_candidate_packs.json`
- `live_integration_candidate_review_queue.json`
- `live_integration_candidate_rollup.json`


## M5C Block 17

Block 17 adds M5C closeout packs and Milestone 5 completion packs on top of the promotion-readiness and live-integration-candidate layers. It keeps the system offline and contract-driven while packaging milestone completion state into replay-safe, provenance-safe artifacts.

### New scripts
- `scripts/build_m5c_closeout_packs.py`
- `scripts/build_milestone5_completion_packs.py`

### New artifacts
- `m5c_closeout_packs.json`
- `m5c_closeout_review_queue.json`
- `m5c_closeout_rollup.json`
- `milestone5_completion_packs.json`
- `milestone5_completion_review_queue.json`
- `milestone5_completion_rollup.json`


## M6A Block 1

Block 1 starts Milestone 6 by materializing a generalized source-control pipeline from ingestion records.

### New script
- `scripts/build_source_control_pipeline.py`

### New artifacts
- `source_records_raw.json`
- `source_records_normalized.json`
- `candidate_matches.json`
- `review_items.json`
- `approved_deltas.json`
- `applied_state_transitions.json`
- `source_control_pipeline_rollup.json`


## M6B Block 1

Block 1 starts M6B by migrating RingCentral and Less Annoying CRM records onto the shared source-control pipeline.

### New script
- `scripts/build_ringcentral_lacrm_migration_packs.py`

### New artifacts
- `ringcentral_lacrm_migration_packs.json`
- `ringcentral_lacrm_migration_review_queue.json`
- `ringcentral_lacrm_migration_rollup.json`
