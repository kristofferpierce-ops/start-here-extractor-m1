# Live Smoke Operator Runbook

This runbook is the human checklist for hosted smoke promotion gating.
Use it when `live_smoke_release_gate.json` reports `"decision": "hold"` or when the hosted smoke matrix needs manual review.

## Core rules

- Treat the release decision artifact as the source of truth for promotion gating.
- Never paste raw access tokens into local terminals, workflow summaries, tickets, or decision artifacts.
- Retry only the affected providers first. Do not rerun the full matrix until the provider-specific issue is understood.

## Required artifacts

The release gate expects these generated artifacts:

- `live_smoke_matrix_summary.json`
- `live_smoke_matrix_summary.md`
- `live_smoke_release_gate.json`
- `live_smoke_release_gate.md`
- provider-specific `live_smoke_summary.json`
- provider-specific `live_smoke_artifact_contract.json`

## Quick inspection commands

From the repo root:

```bash
python ./scripts/live_smoke_matrix.py gate \
  --providers gdrive,dropbox,graph \
  --required-providers gdrive,dropbox,graph \
  --artifacts-root ./artifacts \
  --out-dir ./out

python ./scripts/live_smoke_release_gate.py \
  --matrix-summary ./out/live_smoke_matrix_summary.json \
  --out-dir ./out
```

## Failure handling by classification

### token-resolution-failed

1. Confirm the provider secret exists in the hosted workflow settings.
2. Run the token command locally and confirm it emits only the expected payload.
3. Rerun the affected provider smoke job.

### auth-failed

1. Confirm the provider token is still valid.
2. Confirm the token has the scopes required by the provider search and download path.
3. Rerun the affected provider smoke job.

### rate-limited

1. Inspect the provider telemetry for throttle counts and retry counts.
2. Wait for the provider cooldown window to pass.
3. Rerun only the affected provider before retrying promotion gating.

### no-remote-zip

1. Confirm the smoke query still resolves to a deterministic ZIP in the provider test location.
2. Confirm the test fixture or remote file was not removed or renamed.
3. Rerun the affected provider smoke job.

## When to hold promotion

Hold promotion when any of these conditions are true:

- a required provider failed the smoke matrix
- a required artifact contract is invalid
- unexpected provider artifacts are mixed into the artifact root
- the release decision artifact reports `"promote": false`

## When promotion can proceed

Promotion can proceed only after:

- the matrix summary gate passes for the required providers
- the release decision artifact reports `"promote": true`
- the operator runbook remains present in the checkout used for the release gate
