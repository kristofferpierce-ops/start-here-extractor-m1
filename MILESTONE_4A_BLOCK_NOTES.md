# Milestone 4A block notes

This block begins Milestone 4 as a generic evidence-governance layer rather than a narrow telephony-only workflow.

Added:
- deterministic summary generation from inventory + bounded preview only
- dangerous-instruction heuristics
- additive governance policy decision separate from the extractor operational policy
- append-only audit JSONL with audit refs
- retention status defaulting

Future-safe design choices:
- governance artifacts use generic names (`summary`, `heuristics_findings`, `policy_decision`, `audit_ref`, `retention_status`)
- the existing runtime `policy` field is preserved as the operational extractor decision
- additive-only schema changes preserve Milestones 1-3 contracts
