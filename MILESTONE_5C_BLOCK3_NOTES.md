# Milestone 5C Block 3 notes

This block adds review decision application and matched/approved state transition scaffolding on top of the ingestion backbone and relationship-memory queue.

## Added
- `src/start_here_extractor/review_decisions.py`
- `scripts/apply_review_decisions.py`
- expanded `tests/test_milestone5c.py`
- README section for the new review-application stage

## Outputs
- `ingestion_state_projection.jsonl`
- `review_decision_journal.jsonl`
- `state_transition_rollup.json`
- `state_transition_rollup.md`
- `relationship_memory_post_review.json`
- `operator_review_queue_post_review.json`
- `operator_review_queue_post_review.md`

## Design choices
- keeps original evidence and ingestion records additive rather than mutating source artifacts in place
- derives deterministic review decision identifiers from queue item identity and normalized decision payload
- preserves provenance refs and governance refs
- marks review resolution in a generic way that can later apply to non-ZIP connector families
- treats `no_match` as a resolved review outcome with `approved` set to `not_applicable`

## Intended next step
- application-stage scaffolding for `approved -> applied` transitions against future target systems
