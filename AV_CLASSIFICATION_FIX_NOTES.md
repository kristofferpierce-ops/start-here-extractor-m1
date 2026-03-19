# AV Classification Fix

This patch fixes a Block 3D issue where a missing AV binary such as `clamscan` on Windows was being misclassified as a malicious result.

## Fixed behavior
- Real AV positive remains `scan.status = malicious` and `policy.decision = reject`
- AV execution failures such as missing binary now become `scan.status = inconclusive` with `scan.av.status = error`
- Policy now downgrades those AV execution failures to `warn` instead of `reject`

## Files changed
- `src/start_here_extractor/scan.py`
- `tests/test_milestone3d.py`
