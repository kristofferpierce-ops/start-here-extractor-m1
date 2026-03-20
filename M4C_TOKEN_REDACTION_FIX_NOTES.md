Milestone 4C token redaction fix

This patch fixes a security issue where cloud access tokens could be persisted into inventory, governance, and monitoring JSON output when token health metadata was attached at runtime.

Changes:
- Added ResolvedAccessToken.to_public_dict() that excludes the raw token
- Updated CLI runtime cloud metadata to use the public token-health view
- Added an extra sanitization step in reporter.py so any accidental token field is stripped before writing records
- Added tests to confirm token values are not persisted in governance or monitoring blocks

Important operational note:
- Any token previously written into JSONL output should be treated as exposed and rotated.
