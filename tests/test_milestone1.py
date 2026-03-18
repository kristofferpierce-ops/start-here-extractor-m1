# ruff: noqa: E402
from __future__ import annotations

import json
import struct
import sys
import zlib
import zipfile
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCHEMA_PATH = ROOT / "schemas" / "inventory.schema.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from start_here_extractor.cli import main


SCHEMA_VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def create_zip(path: Path, members: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> None:
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def create_cp437_zip(path: Path, filename: str, payload: bytes) -> None:
    filename_bytes = filename.encode("cp437")
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    compressed = payload
    compressed_size = len(compressed)
    uncompressed_size = len(payload)

    local_header = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50,
        20,
        0,
        0,
        0,
        0,
        crc,
        compressed_size,
        uncompressed_size,
        len(filename_bytes),
        0,
    )
    central_header = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50,
        20,
        20,
        0,
        0,
        0,
        0,
        crc,
        compressed_size,
        uncompressed_size,
        len(filename_bytes),
        0,
        0,
        0,
        0,
        0,
        0,
    )
    local_record = local_header + filename_bytes + compressed
    central_record = central_header + filename_bytes
    central_offset = len(local_record)
    end_record = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        1,
        1,
        len(central_record),
        central_offset,
        0,
    )
    path.write_bytes(local_record + central_record + end_record)


def load_inventory(path: Path) -> dict:
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    lines = [line for line in raw.decode("utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    errors = list(SCHEMA_VALIDATOR.iter_errors(record))
    assert not errors, "; ".join(error.message for error in errors)
    return record


def run_cli(tmp_path: Path, zip_path: Path, *extra: str) -> tuple[dict, Path]:
    output_dir = tmp_path / "out"
    report_dir = tmp_path / "reports"
    exit_code = main([str(zip_path), "--output-dir", str(output_dir), "--report-dir", str(report_dir), *extra])
    assert exit_code in (0, 1)
    inventories = list(report_dir.glob("*.inventory.jsonl"))
    assert len(inventories) == 1
    inventory_path = inventories[0]
    return load_inventory(inventory_path), inventory_path


def test_t1_case_insensitive_found(tmp_path: Path) -> None:
    zip_path = tmp_path / "t1.zip"
    create_zip(zip_path, {"START HERE.TXT": b"hello world"})
    inventory, _ = run_cli(tmp_path, zip_path)
    assert inventory["outcome"] == "extracted"
    assert inventory["selected_candidate"]["name"] == "START HERE.TXT"


def test_t2_prefer_txt_over_md(tmp_path: Path) -> None:
    zip_path = tmp_path / "t2.zip"
    create_zip(zip_path, {"Start Here.md": b"markdown", "START HERE.TXT": b"text"})
    inventory, _ = run_cli(tmp_path, zip_path)
    assert inventory["outcome"] == "extracted"
    assert inventory["selected_candidate"]["extension"] == ".txt"


def test_t3_error_on_multiple_when_policy_error(tmp_path: Path) -> None:
    zip_path = tmp_path / "t3.zip"
    create_zip(zip_path, {"Start Here.md": b"markdown", "START HERE.TXT": b"text"})
    inventory, _ = run_cli(tmp_path, zip_path, "--tie-policy", "error")
    assert inventory["outcome"] == "error"
    assert inventory["errors"][0]["type"] == "MultipleMatchesError"


def test_t4_zip_slip_rejected(tmp_path: Path) -> None:
    zip_path = tmp_path / "t4.zip"
    create_zip(zip_path, {"../Start Here.txt": b"evil"})
    inventory, _ = run_cli(tmp_path, zip_path)
    assert inventory["outcome"] == "error"
    assert inventory["errors"][0]["type"] == "PathTraversalRisk"


def test_t5_declared_size_over_cap(tmp_path: Path) -> None:
    zip_path = tmp_path / "t5.zip"
    create_zip(zip_path, {"Start Here.txt": b"A" * 200})
    inventory, _ = run_cli(tmp_path, zip_path, "--max-member-bytes", "100")
    assert inventory["outcome"] == "error"
    assert inventory["errors"][0]["type"] == "ZipBombRisk"


def test_t6_ratio_over_cap(tmp_path: Path) -> None:
    zip_path = tmp_path / "t6.zip"
    create_zip(zip_path, {"Start Here.txt": b"A" * 20000})
    inventory, _ = run_cli(tmp_path, zip_path, "--max-ratio", "1.1")
    assert inventory["outcome"] == "error"
    assert inventory["errors"][0]["type"] == "ZipBombRisk"


def test_t7_utf16_preview_readable(tmp_path: Path) -> None:
    zip_path = tmp_path / "t7.zip"
    payload = "Hello from utf16".encode("utf-16")
    create_zip(zip_path, {"Start Here.txt": payload})
    inventory, _ = run_cli(tmp_path, zip_path)
    assert inventory["outcome"] == "extracted"
    assert inventory["preview"]["encoding"].startswith("utf-16")
    assert "Hello from utf16" in inventory["preview"]["text"]


@pytest.mark.parametrize("member_name", ["/Start Here.txt", "C:/Start Here.txt"])
def test_absolute_path_rejected(tmp_path: Path, member_name: str) -> None:
    zip_path = tmp_path / "abs.zip"
    create_zip(zip_path, {member_name: b"evil"})
    inventory, _ = run_cli(tmp_path, zip_path)
    assert inventory["outcome"] == "error"
    assert inventory["errors"][0]["type"] == "PathTraversalRisk"


def test_no_match_still_emits_inventory(tmp_path: Path) -> None:
    zip_path = tmp_path / "nomatch.zip"
    create_zip(zip_path, {"readme.txt": b"no start here present"})
    inventory, inventory_path = run_cli(tmp_path, zip_path)
    assert inventory_path.exists()
    assert inventory["outcome"] == "no_match"
    assert inventory["start_here"] is None
    assert inventory["errors"][0]["type"] == "NoMatchError"


def test_cp437_non_ascii_directory_name_decodes_cleanly(tmp_path: Path) -> None:
    zip_path = tmp_path / "cp437.zip"
    create_cp437_zip(zip_path, "niño/START HERE.TXT", b"hola")
    inventory, _ = run_cli(tmp_path, zip_path)
    assert inventory["outcome"] == "extracted"
    assert inventory["selected_candidate"]["name"] == "niño/START HERE.TXT"
    assert inventory["start_here"] == "niño/START HERE.TXT"
