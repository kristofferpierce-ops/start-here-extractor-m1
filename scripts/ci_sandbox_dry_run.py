from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path
import zipfile


def make_mismatch_zip(target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("START HERE.TXT", b"hello")
    data = bytearray(target.read_bytes())
    name_len = struct.unpack_from("<H", data, 26)[0]
    replacement = b"START THER.TXT"
    if len(replacement) != name_len:
        raise RuntimeError("Replacement name length mismatch")
    start = 30
    data[start:start + name_len] = replacement
    target.write_bytes(data)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    work = repo_root / "out" / "ci_sandbox"
    extracted = work / "extracted"
    reports = work / "reports"
    artifacts = work / "sandbox_artifacts"
    work.mkdir(parents=True, exist_ok=True)
    mismatch = work / "mismatch.zip"
    make_mismatch_zip(mismatch)

    cmd = [
        sys.executable,
        "-m",
        "start_here_extractor.cli",
        str(mismatch),
        "--output-dir",
        str(extracted),
        "--report-dir",
        str(reports),
        "--sandbox-platform",
        "windows-sandbox",
        "--sandbox-dry-run",
        "--sandbox-root",
        str(artifacts),
    ]
    subprocess.run(cmd, cwd=repo_root, check=True)

    inventory = reports / "mismatch.inventory.jsonl"
    record = json.loads(inventory.read_text(encoding="utf-8").splitlines()[0])

    assert record["outcome"] == "inspected", record
    assert record["policy"]["decision"] == "sandbox", record
    assert record["sandbox"]["enabled"] is True, record
    assert record["sandbox"]["dry_run"] is True, record

    staging = Path(record["sandbox"]["config_path"]).parent
    if not staging.is_absolute():
        staging = repo_root / staging
    assert staging.exists(), staging
    wsb_files = list(staging.glob("*.wsb"))
    ps_files = list(staging.glob("*.ps1"))
    assert wsb_files, "No .wsb file generated"
    assert ps_files, "No sandbox PowerShell script generated"

    print("ci sandbox dry run ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
