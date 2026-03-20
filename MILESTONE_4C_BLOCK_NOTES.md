Milestone 4C continues the generic evidence-governance layer with provider hardening and operational monitoring.

This block adds:
- runtime cloud token resolution by direct token or shell command
- token-health hints for near-expiry and expired tokens
- monitoring JSONL append streams and monitoring_ref in inventory records
- governance links to monitoring streams and sandbox snapshot references
- stronger review_required semantics that generalize beyond ZIP-only processing

Future-safe design choices:
- no provider-specific tables or UI naming were introduced
- monitoring is generic and can later be reused for jobs, invoices, labor, and other evidence streams
- sandbox snapshot references are surfaced as governance evidence instead of hidden runtime state
