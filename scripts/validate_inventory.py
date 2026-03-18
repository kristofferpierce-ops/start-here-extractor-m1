from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "inventory.schema.json"


def load_validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_jsonl_file(path: Path, validator: Draft202012Validator) -> int:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} contains a UTF-8 BOM, which is not allowed for JSON Lines")

    text = raw.decode("utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"{path} did not contain any JSONL records")

    count = 0
    for index, line in enumerate(lines, start=1):
        record = json.loads(line)
        errors = sorted(validator.iter_errors(record), key=lambda err: err.path)
        if errors:
            messages = "; ".join(error.message for error in errors)
            raise ValueError(f"{path}:{index} failed schema validation: {messages}")
        count += 1
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate inventory JSONL files against the packaged schema")
    parser.add_argument("paths", nargs="+", help="JSONL files to validate")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Path to the JSON schema file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validator = load_validator(Path(args.schema))

    total_files = 0
    total_records = 0
    for raw_path in args.paths:
        path = Path(raw_path)
        records = validate_jsonl_file(path, validator)
        total_files += 1
        total_records += records
        print(f"validated {records} record(s) in {path}")

    print(f"ok: validated {total_records} record(s) across {total_files} file(s)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
