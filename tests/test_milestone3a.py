# ruff: noqa: E402
from __future__ import annotations

import json
import shutil
import struct
import sys
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCHEMA_PATH = ROOT / "schemas" / "inventory.schema.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from start_here_extractor.cli import main
from start_here_extractor.io.jsonl_writer import JsonlWriter
from start_here_extractor.net.retry import with_retries
from start_here_extractor.errors import RetryableOperationError


def create_zip(path: Path, members: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> None:
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def load_single_inventory(report_dir: Path) -> dict:
    inventory = next(report_dir.glob("*.inventory.jsonl"))
    return json.loads(inventory.read_text(encoding="utf-8").splitlines()[0])


def run_cli(tmp_path: Path, zip_path: Path, *extra: str) -> tuple[int, dict]:
    output_dir = tmp_path / "out"
    report_dir = tmp_path / "reports"
    exit_code = main([str(zip_path), "--output-dir", str(output_dir), "--report-dir", str(report_dir), *extra])
    return exit_code, load_single_inventory(report_dir)


def patch_local_header_name(zip_path: Path, replacement_name: str) -> None:
    data = bytearray(zip_path.read_bytes())
    name_len = struct.unpack_from("<H", data, 26)[0]
    replacement = replacement_name.encode("utf-8")
    assert len(replacement) == name_len
    start = 30
    data[start : start + name_len] = replacement
    zip_path.write_bytes(data)


def create_data_descriptor_zip(path: Path, filename: str, payload: bytes) -> None:
    name_bytes = filename.encode("utf-8")
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    compressed = payload
    compressed_size = len(compressed)
    uncompressed_size = len(payload)
    local_header = struct.pack(
        "<IHHHHHIIIHH",
        0x04034B50,
        20,
        0x08,
        0,
        0,
        0,
        0,
        0,
        0,
        len(name_bytes),
        0,
    )
    data_descriptor = struct.pack("<IIII", 0x08074B50, crc, compressed_size, uncompressed_size)
    central_header = struct.pack(
        "<IHHHHHHIIIHHHHHII",
        0x02014B50,
        20,
        20,
        0x08,
        0,
        0,
        0,
        crc,
        compressed_size,
        uncompressed_size,
        len(name_bytes),
        0,
        0,
        0,
        0,
        0,
        0,
    )
    local_record = local_header + name_bytes + compressed + data_descriptor
    central_offset = len(local_record)
    central_record = central_header + name_bytes
    eocd = struct.pack(
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
    path.write_bytes(local_record + central_record + eocd)


def test_strict_zip_validation_flags_central_local_name_mismatch(tmp_path: Path) -> None:
    zip_path = tmp_path / "mismatch.zip"
    create_zip(zip_path, {"START HERE.TXT": b"hello"}, compression=zipfile.ZIP_STORED)
    patch_local_header_name(zip_path, "START THER.TXT")

    exit_code, inventory = run_cli(tmp_path, zip_path)
    assert exit_code == 1
    assert inventory["outcome"] == "error"
    assert inventory["policy"]["decision"] == "reject"
    assert any(flag.startswith("central-local-name-mismatch:") for flag in inventory["zip_hardening"]["flags"])


def test_strict_zip_validation_flags_data_descriptor_ambiguity(tmp_path: Path) -> None:
    zip_path = tmp_path / "descriptor.zip"
    create_data_descriptor_zip(zip_path, "START HERE.TXT", b"descriptor payload")

    exit_code, inventory = run_cli(tmp_path, zip_path)
    assert exit_code == 1
    assert inventory["outcome"] == "error"
    assert inventory["policy"]["decision"] == "reject"
    assert any(flag.startswith("data-descriptor-ambiguity:") for flag in inventory["zip_hardening"]["flags"])


def test_strict_zip_validation_flags_duplicate_names(tmp_path: Path) -> None:
    zip_path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("START HERE.TXT", b"one")
        archive.writestr("START HERE.TXT", b"two")

    exit_code, inventory = run_cli(tmp_path, zip_path)
    assert exit_code == 1
    assert inventory["outcome"] == "error"
    assert any(flag.startswith("duplicate-entry-name:") for flag in inventory["zip_hardening"]["flags"])


def test_with_retries_honors_retry_after(monkeypatch) -> None:
    sleeps: list[float] = []
    state = {"attempts": 0}

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    def flaky() -> str:
        state["attempts"] += 1
        if state["attempts"] == 1:
            raise RetryableOperationError("wait", retry_after_seconds=1.5)
        return "ok"

    result = with_retries(flaky, sleep_fn=fake_sleep)
    assert result == "ok"
    assert sleeps == [1.5]


def test_jsonl_writer_durable_mode_calls_fsync(monkeypatch, tmp_path: Path) -> None:
    fsync_calls: list[int] = []

    def fake_fsync(fd: int) -> None:
        fsync_calls.append(fd)

    monkeypatch.setattr("start_here_extractor.io.jsonl_writer.os.fsync", fake_fsync)
    out_path = tmp_path / "out" / "records.jsonl"
    with JsonlWriter(out_path, durable=True) as writer:
        writer.write_record({"ok": True})
    assert len(fsync_calls) == 1
    assert out_path.read_text(encoding="utf-8") == '{"ok":true}\n'


def test_outer_program_root_folder_name_is_not_hardcoded(tmp_path: Path) -> None:
    renamed_root = tmp_path / "arbitrary-root-name"
    shutil.copytree(ROOT / "src", renamed_root / "src")
    copied_cli = renamed_root / "src" / "start_here_extractor" / "cli.py"
    copied_reader = renamed_root / "src" / "start_here_extractor" / "reader.py"
    assert copied_cli.exists()
    assert copied_reader.exists()
    assert "start_here_extractor_m" not in copied_cli.read_text(encoding="utf-8")
    assert "start_here_extractor_m" not in copied_reader.read_text(encoding="utf-8")
