# ruff: noqa: E402
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from start_here_extractor.cli import main


def create_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def test_batch_mode_orders_zip_processing_deterministically(tmp_path: Path) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    create_zip(incoming / "b_second.zip", {"START HERE.TXT": b"b"})
    create_zip(incoming / "A_first.zip", {"START HERE.TXT": b"a"})
    create_zip(incoming / "c_third.zip", {"START HERE.TXT": b"c"})

    output_dir = tmp_path / "out"
    report_dir = tmp_path / "reports"
    jsonl_out = report_dir / "sorted.jsonl"

    exit_code = main(
        [
            "--all",
            "--root",
            str(incoming),
            "--output-dir",
            str(output_dir),
            "--report-dir",
            str(report_dir),
            "--jsonl-out",
            str(jsonl_out),
        ]
    )
    assert exit_code == 0

    lines = [line for line in jsonl_out.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [json.loads(line) for line in lines]
    ordered_names = [Path(record["zip_path"]).name for record in records]
    assert ordered_names == ["A_first.zip", "b_second.zip", "c_third.zip"]
