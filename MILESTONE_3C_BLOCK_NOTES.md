# Milestone 3C Block Notes

This block adds the first real cloud-provider implementation slice for Milestone 3.

## Scope

Implemented:
- Google Drive locator with `files.list` paging and `files.get?alt=media` downloads
- Dropbox locator with `/files/search_v2`, cursor pagination, and `/files/download`
- Microsoft Graph locator with DriveItem search, `@odata.nextLink`, and `/content` downloads
- shared HTTP request helpers with retry/backoff integration
- optional CLI remote smoke mode using `--cloud-provider`
- mocked tests for paging, throttling, and download behavior

Not claimed yet:
- full OAuth installed-app flows or token refresh brokers
- live CI against provider credentials
- cloud-backed batch concurrency orchestration beyond the current local/batch pipeline
- provider-specific malware/abuse prompts beyond Google Drive's acknowledgment flag

## Backward compatibility

- Milestone 1 public interfaces preserved
- Milestone 2 JSON contract preserved
- Milestone 3 additive inventory fields preserved
- outer project root folder name remains irrelevant

## Suggested next block

The next highest-value block after 3C is scan integration and policy-driven gating:
- pluggable AV engines
- optional YARA support
- scan result influence on policy decisions
- mocked CI-safe scan tests
