# Phase 19 Step 16 — Extractor Evidence Index

## Purpose

Step 16 brings `start_here_extractor_m1_completion` into the integration path as the evidence and governance subsystem.

It consumes a Phase 19 release checkpoint JSON produced by the platform repo and creates a redacted evidence pack.

## What it does

- reads `phase19_release_checkpoint_*.json` from the workspace backups folder
- computes a SHA-256 hash of the checkpoint
- summarizes runtime state, integration counts, LACRM safety state, and repo boundaries
- redacts phone numbers, email addresses, token-like values, and raw payload-like fields
- writes a redacted evidence index and summary JSON

## What it does not do

- does not call LACRM
- does not patch the bridge
- does not mutate platform, bridge, or extractor runtime databases
- does not enable live writes
- does not commit secrets

## Command

From the extractor repo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\phase19_index_release_checkpoint.ps1
```

The default output goes to:

```text
C:\Users\krist\Desktop\unified_pool_service_platform_build\backups\phase19_extractor_evidence_<timestamp>
```

## Commit guard

Stage only:

```text
src/start_here_extractor/phase19_evidence.py
scripts/phase19_index_release_checkpoint.ps1
PHASE19_STEP16_EXTRACTOR_EVIDENCE.md
tests/test_phase19_evidence.py
```

Do not stage generated evidence packs, local outputs, credentials, tokens, or runtime databases.
