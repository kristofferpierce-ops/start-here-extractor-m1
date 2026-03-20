# Milestone 5A block notes

This block starts Milestone 5 as a governed action-orchestration layer on top of the existing evidence-processing subsystem.

Included:
- generic remediation playbook runner
- role-based authorization core
- immutable append-only action audit events
- idempotency keys and replay-safe skipping
- dedicated `start-here-playbook` command

Future-safe choices:
- names are generic (`playbook`, `action`, `authorization`, `audit`) rather than ZIP-only
- action ledger is append-only and can later govern jobs, invoices, labor, and purchasing evidence
- dry-run is first-class and separate from live action execution
