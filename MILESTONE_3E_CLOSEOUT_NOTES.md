# Milestone 3E Closeout Notes

This block is the Milestone 3 closeout / release-hardening package.

## Primary additions

- No-secrets default CI matrix on Windows, macOS, and Linux
- Windows-only CI smoke script for sandbox **dry-run** artifact generation
- Manual `workflow_dispatch` live-provider smoke workflow
- Local credential hygiene via `.gitignore`
- Milestone 3 release checklist

## Why this block exists

Milestone 3 already has:

- strict ZIP hardening and policy escalation
- sandbox dry-run generation
- real remote locators
- AV + optional YARA scan integration

The remaining work is release discipline:

- safe CI defaults
- controlled live test entry points
- reproducible release checklists
- secret hygiene

## Notes

- The live-provider workflow is intentionally **manual**
- It requires repository secrets and should not run on every push
- The default CI workflow does not require secrets
- The default CI workflow does not launch real Windows Sandbox; it only verifies dry-run artifact generation
