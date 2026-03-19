# ruff: noqa: E402
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCHEMA_PATH = ROOT / "schemas" / "inventory.schema.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from start_here_extractor.cli import main


SCHEMA_VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def create_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def load_jsonl(path: Path) -> list[dict]:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    lines = raw.decode("utf-8").splitlines()
    assert lines
    records = [json.loads(line) for line in lines if line.strip()]
    for record in records:
        errors = list(SCHEMA_VALIDATOR.iter_errors(record))
        assert not errors, "; ".join(error.message for error in errors)
    return records


def test_batch_jsonl_emits_one_valid_record_per_zip_and_preserves_contract(tmp_path: Path) -> None:
    good_zip = tmp_path / "ok.zip"
    ambiguous_zip = tmp_path / "ambiguous.zip"
    bad_zip = tmp_path / "bad.zip"

    create_zip(good_zip, {"START HERE.TXT": b"hello from good zip"})
    create_zip(ambiguous_zip, {"START HERE.TXT": b"one", "Start Here.md": b"two"})
    bad_zip.write_text("not a zip archive", encoding="utf-8")

    output_dir = tmp_path / "out"
    report_dir = tmp_path / "reports"
    jsonl_out = report_dir / "inventories.jsonl"

    exit_code = main(
        [
            "--all",
            str(good_zip),
            str(ambiguous_zip),
            str(bad_zip),
            "--tie-policy",
            "error",
            "--output-dir",
            str(output_dir),
            "--report-dir",
            str(report_dir),
            "--jsonl-out",
            str(jsonl_out),
        ]
    )
    assert exit_code == 1

    records = load_jsonl(jsonl_out)
    assert len(records) == 3
    assert [Path(record["zip_path"]).name for record in records] == ["ambiguous.zip", "bad.zip", "ok.zip"]

    single_report_dir = tmp_path / "single_reports"
    single_output_dir = tmp_path / "single_out"
    single_exit = main(
        [
            str(good_zip),
            "--output-dir",
            str(single_output_dir),
            "--report-dir",
            str(single_report_dir),
        ]
    )
    assert single_exit == 0
    single_record = load_jsonl(next(single_report_dir.glob("*.inventory.jsonl")))[0]

    good_record = next(record for record in records if Path(record["zip_path"]).name == "ok.zip")
    assert set(good_record.keys()) == set(single_record.keys())
    assert good_record["outcome"] == "extracted"

    ambiguous_record = next(record for record in records if Path(record["zip_path"]).name == "ambiguous.zip")
    assert ambiguous_record["outcome"] == "error"
    assert ambiguous_record["errors"][0]["type"] == "MultipleMatchesError"

    bad_record = next(record for record in records if Path(record["zip_path"]).name == "bad.zip")
    assert bad_record["outcome"] == "error"
    assert bad_record["errors"][0]["type"] == "BadZipFile"


def test_jsonl_append_mode_keeps_file_parseable_across_restarts(tmp_path: Path) -> None:
    first_zip = tmp_path / "first.zip"
    second_zip = tmp_path / "second.zip"
    create_zip(first_zip, {"START HERE.TXT": b"first"})
    create_zip(second_zip, {"START HERE.TXT": b"second"})

    output_dir = tmp_path / "out"
    report_dir = tmp_path / "reports"
    jsonl_out = report_dir / "appendable.jsonl"

    exit_one = main(
        [
            "--all",
            str(first_zip),
            "--output-dir",
            str(output_dir),
            "--report-dir",
            str(report_dir),
            "--jsonl-out",
            str(jsonl_out),
        ]
    )
    exit_two = main(
        [
            "--all",
            str(second_zip),
            "--output-dir",
            str(output_dir),
            "--report-dir",
            str(report_dir),
            "--jsonl-out",
            str(jsonl_out),
        ]
    )
    assert exit_one == 0
    assert exit_two == 0

    records = load_jsonl(jsonl_out)
    assert len(records) == 2
    assert [Path(record["zip_path"]).name for record in records] == ["first.zip", "second.zip"]
