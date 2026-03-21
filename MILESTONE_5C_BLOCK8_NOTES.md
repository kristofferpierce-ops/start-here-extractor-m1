# M5C Block 8 notes

This block adds runner adapter interfaces and collector normalization contracts on top of the Block 7 runner-stub layer.

## Added in this block
- stable runner-interface contracts between runner jobs and external result payloads
- catalog-driven interface selection keyed to runner family, transport, target system, and adapter family
- canonical normalization of raw external runner payloads into collector-ready outcomes
- review queues for interface routing and collector normalization mismatches
- markdown and JSON rollups for both new layers

## Why it matters
- keeps future real runner adapters behind stable contracts instead of hardcoded one-off handlers
- lets different external payload shapes normalize into one collector shape before Block 7 outcome collection
- preserves evidence, provenance, and execution journaling boundaries
- keeps the pipeline connector-neutral while making future target-specific adapters easier to add
