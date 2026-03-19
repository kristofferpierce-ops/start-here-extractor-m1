# ruff: noqa: E402
from __future__ import annotations

import json
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from start_here_extractor.cli import main
from start_here_extractor.sandbox import SandboxJobRequest, WindowsSandboxRunner


def create_zip(path: Path, members: dict[str, bytes], compression: int = zipfile.ZIP_STORED) -> None:
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def patch_local_header_name(zip_path: Path, replacement_name: str) -> None:
    data = bytearray(zip_path.read_bytes())
    name_len = struct.unpack_from("<H", data, 26)[0]
    replacement = replacement_name.encode("utf-8")
    assert len(replacement) == name_len
    start = 30
    data[start : start + name_len] = replacement
    zip_path.write_bytes(data)


def load_single_inventory(report_dir: Path) -> dict:
    inventory = next(report_dir.glob("*.inventory.jsonl"))
    return json.loads(inventory.read_text(encoding="utf-8").splitlines()[0])


def test_windows_sandbox_wsb_xml_contains_required_hardening(tmp_path: Path) -> None:
    runner = WindowsSandboxRunner(sandbox_exe=tmp_path / "WindowsSandbox.exe")
    request = SandboxJobRequest(
        job_id="job-1",
        zip_path=tmp_path / "sample.zip",
        host_staging_dir=tmp_path / "staging",
        host_results_dir=tmp_path / "results",
        timeout_seconds=90,
    )
    xml = runner.render_wsb_xml(request)
    assert "<Networking>Disable</Networking>" in xml
    assert "<ClipboardRedirection>Disable</ClipboardRedirection>" in xml
    assert "<vGPU>Disable</vGPU>" in xml
    assert "<ReadOnly>true</ReadOnly>" in xml
    assert "<ReadOnly>false</ReadOnly>" in xml
    assert "<LogonCommand>" in xml


def test_windows_sandbox_dry_run_writes_config_and_script(tmp_path: Path) -> None:
    zip_path = tmp_path / "sample.zip"
    create_zip(zip_path, {"START HERE.TXT": b"hello"})
    runner = WindowsSandboxRunner(sandbox_exe=tmp_path / "WindowsSandbox.exe")
    request = SandboxJobRequest(
        job_id="job-2",
        zip_path=zip_path,
        host_staging_dir=tmp_path / "staging",
        host_results_dir=tmp_path / "results",
        command_line='Write-Host "inside sandbox"',
    )
    result = runner.run(request, dry_run=True)
    assert result.enabled is True
    assert result.platform == "windows-sandbox"
    assert result.dry_run is True
    assert Path(result.config_path).exists()
    assert Path(result.command_path).exists()
    assert Path(result.config_path).suffix == ".wsb"
    script_text = Path(result.command_path).read_text(encoding="utf-8")
    assert "job.completed.json" in script_text
    assert 'Write-Host "inside sandbox"' in script_text
    assert any(note == "dry-run" for note in result.notes)


def test_cli_sandbox_dry_run_for_suspicious_zip_emits_sandbox_block(tmp_path: Path) -> None:
    zip_path = tmp_path / "mismatch.zip"
    create_zip(zip_path, {"START HERE.TXT": b"hello"}, compression=zipfile.ZIP_STORED)
    patch_local_header_name(zip_path, "START THER.TXT")

    output_dir = tmp_path / "out"
    report_dir = tmp_path / "reports"
    sandbox_root = tmp_path / "sandbox-artifacts"
    exit_code = main(
        [
            str(zip_path),
            "--output-dir",
            str(output_dir),
            "--report-dir",
            str(report_dir),
            "--sandbox-platform",
            "windows-sandbox",
            "--sandbox-dry-run",
            "--sandbox-root",
            str(sandbox_root),
        ]
    )
    assert exit_code == 0
    inventory = load_single_inventory(report_dir)
    assert inventory["outcome"] == "inspected"
    assert inventory["policy"]["decision"] == "sandbox"
    assert inventory["sandbox"]["enabled"] is True
    assert inventory["sandbox"]["dry_run"] is True
    assert inventory["sandbox"]["platform"] == "windows-sandbox"
    assert Path(inventory["sandbox"]["config_path"]).exists()
    assert Path(inventory["sandbox"]["command_path"]).exists()
    assert inventory["sandbox"]["sentinel_path"].endswith("job.completed.json")
    assert any(note == "dry-run" for note in inventory["sandbox"]["notes"])
