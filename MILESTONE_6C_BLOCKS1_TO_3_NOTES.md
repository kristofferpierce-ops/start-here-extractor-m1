Milestone 6C bundled pass 1 through 3

Scope
- durable IDs and lineage packs
- replay-safe ingestion controls
- lineage/replay readiness packs

Outputs
- durable_lineage_packs.json
- durable_lineage_review_queue.json
- durable_lineage_rollup.json
- replay_safe_ingestion_controls.json
- replay_safe_ingestion_review_queue.json
- replay_safe_ingestion_rollup.json
- lineage_replay_readiness_packs.json
- lineage_replay_readiness_review_queue.json
- lineage_replay_readiness_rollup.json

Design notes
- source-control pipeline remains the canonical basis for raw and normalized references
- RingCentral/LACRM migration packs are classified inputs, not execution outputs
- replay-safe controls remain offline and idempotency-oriented
- readiness packs summarize whether a source is safe to replay or blocked for review
