# Milestone 1 build notes

This package was built directly from the uploaded blueprint PDF and technical overview.

Implemented modules:

- `locator.py`
- `inspector.py`
- `matcher.py`
- `extractor.py`
- `reader.py`
- `reporter.py`
- `processor.py`
- `cli.py`

Implemented support files:

- `pyproject.toml`
- `schemas/inventory.schema.json`
- `scripts/start_here_helper.ps1`
- `scripts/validate_inventory.py`
- `.github/workflows/tests.yml`
- `README.md`
- `tests/` acceptance + hardening suite
- `MILESTONE_1_SIGNOFF_CHECKLIST.md`

Key milestone choices made now:

- normalization treats `START HERE`, `start_here`, and `start-here` as the same basename token
- `.txt` then `.md` are the preferred extension order
- flatten output remains the default extraction mode
- AV remains advisory only
- strict CRC verification remains opt-in
- JSON inventory is emitted as UTF-8 JSONL with newline termination
- CI now runs on Windows, macOS, and Linux
- CI now includes lint and schema validation

Still intentionally configurable:

- exact alias list
- final size and ratio caps
- per-ZIP JSONL vs future append-only batch JSONL strategy
- AV command and policy
- release/distribution target (private repo, GitHub release, PyPI, internal artifact store)
