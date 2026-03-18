# Milestone 1 signoff checklist

## Implementation status

- [x] Locator implemented for explicit ZIP paths and recursive roots
- [x] Inspector implemented with entry caps and suspicious-path metadata
- [x] Matcher implemented with deterministic ambiguity handling
- [x] Extractor implemented for single-member bounded extraction
- [x] Zip Slip rejection implemented for parent traversal, absolute root, UNC, and Windows-drive paths
- [x] ZIP bomb protections implemented for declared size, compression ratio, and streamed-byte caps
- [x] Reader implemented with bounded preview and UTF-16 fallback
- [x] Advisory AV hook implemented
- [x] Reporter emits UTF-8 JSONL inventory with trailing newline
- [x] Stable schema included for inventory records
- [x] CLI orchestrates locate -> inspect -> match -> extract -> AV -> preview -> report
- [x] PowerShell helper included

## Test and CI status

- [x] Acceptance tests T1-T7 implemented
- [x] Explicit absolute-path tests implemented
- [x] Explicit no-match inventory test implemented
- [x] Explicit CP437/non-ASCII filename handling test implemented
- [x] Schema validation covered in CI
- [x] Lint covered in CI
- [x] CI matrix includes Windows, macOS, and Linux

## Security review checkpoints

- [x] No unfiltered `extractall()` usage
- [x] Suspicious member paths are rejected before extraction
- [x] Extraction is bounded and cleans up partial files on streamed overflow
- [x] AV is telemetry only, not a trust boundary
- [x] Inventory is produced for extracted, error, and no-match outcomes

## Manual release checklist

- [ ] Run CI on the target repository
- [ ] Review configured size/ratio caps against production expectations
- [ ] Decide final alias policy for START HERE basenames and extensions
- [ ] Decide production AV command policy by platform
- [ ] Tag release / package artifact for delivery
- [ ] Publish or hand off release bundle

## Signoff summary

This package is ready for Milestone 1 release-candidate use, subject to the manual release checklist above.
