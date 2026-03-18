I am uploading the current **Milestone 1 START HERE extractor release-candidate package** plus the two Milestone 1 PDFs.

Use the uploaded package as the implementation source of truth and do a **strict release-candidate audit** against the PDFs.

## Your goals

1. Verify whether Milestone 1 is now truly complete
2. Identify any remaining mismatches between implementation and the PDFs
3. Separate:
   - code-complete items
   - docs/packaging gaps
   - manual release/signoff items
4. Recommend the smallest final set of changes needed to call Milestone 1 done

## Important instructions

- Use the uploaded code package as the primary implementation source of truth
- Compare it directly against both Milestone 1 PDFs
- Do not suggest Milestone 2 work unless it blocks Milestone 1 release
- Be explicit about whether any remaining items are:
  - required for Milestone 1 completion
  - optional polish
  - Milestone 2 only

## Specifically check these areas

- JSONL output format and schema stability
- CLI behavior and documented flags
- inspect -> match -> extract -> AV -> preview -> report orchestration
- Zip Slip defenses
- ZIP bomb defenses
- no-match behavior and inventory emission
- UTF-16 preview behavior
- absolute path handling
- non-ASCII filename handling
- schema validation tooling
- CI matrix and steps
- PowerShell helper parity with the documented workflow
- package cleanliness:
  - no pyc or cache junk
  - examples still valid
  - docs align with actual behavior

## Deliverables I want back

1. a Milestone 1 release audit
2. a pass/fail judgment for Milestone 1
3. a list of exact remaining required edits, if any
4. a release checklist for me to execute locally
5. if needed, a final tiny patch list rather than a rewrite
