# Milestone 6A Block 1 Notes

This block starts Milestone 6 by building a generalized source-control pipeline on top of existing ingestion records.

It adds a connector-neutral source pipeline that materializes:
- source records raw
- source records normalized
- candidate matches
- review items
- approved deltas
- applied state transitions

This is the first concrete bridge from the M5 evidence/replay subsystem into the broader operating-core raw → normalized → matched → approved → applied backbone.
