# ruff: noqa: E402
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from start_here_extractor.processor import process_zip
from start_here_extractor.scan import ScanConfig, scan_extracted_path
from start_here_extractor.types import ExtractSettings, Limits, MatchPolicy


def create_zip(path: Path, members: dict[str, bytes], compression: int = zipfile.ZIP_STORED) -> None:
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


class DummyCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_scan_clamav_infected_marks_malicious(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")

    def fake_run(*args, **kwargs):
        return DummyCompleted(1, stdout="Eicar-Test-Signature FOUND")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = scan_extracted_path(sample, ScanConfig(av_engine="clamav", av_command="clamscan {path}"))
    assert result["status"] == "malicious"
    assert result["av"]["status"] == "infected"
    assert result["findings"]


def test_scan_yara_match_populates_ruleset(monkeypatch, tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")

    def fake_run(command, **kwargs):
        assert "sample-rules" not in command  # ruleset id is inventory metadata only
        return DummyCompleted(0, stdout="rule_sample sample.txt")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = scan_extracted_path(
        sample,
        ScanConfig(
            yara_command="yara {compiled_flag} {rules} {path}",
            yara_rules="rules/sample.yar",
            yara_ruleset_id="sample-rules",
        ),
    )
    assert result["status"] == "malicious"
    assert result["yara"]["status"] == "match"
    assert result["yara"]["ruleset_id"] == "sample-rules"
    assert result["yara"]["matches"] == ["rule_sample sample.txt"]


def test_compiled_yara_requires_explicit_acknowledgement(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    result = scan_extracted_path(
        sample,
        ScanConfig(
            yara_command="yara {compiled_flag} {rules} {path}",
            yara_rules="rules/sample.yarc",
            yara_compiled_rules=True,
            yara_allow_compiled_rules=False,
        ),
    )
    assert result["status"] == "inconclusive"
    assert result["yara"]["status"] == "blocked"
    assert result["yara"]["reason"] == "compiled-rules-disallowed"


def test_process_zip_rejects_after_malicious_scan(monkeypatch, tmp_path: Path) -> None:
    zip_path = tmp_path / "sample.zip"
    create_zip(zip_path, {"START HERE.TXT": b"hello malware"})

    def fake_run(*args, **kwargs):
        return DummyCompleted(1, stdout="Eicar-Test-Signature FOUND")

    monkeypatch.setattr(subprocess, "run", fake_run)

    output_dir = tmp_path / "out"
    result = process_zip(
        zip_path,
        output_dir,
        Limits(),
        MatchPolicy(allowed_basenames=["start here"], allowed_extensions=[".txt", ".md"], tie_policy="prefer", preferred_extensions=[".txt", ".md"]),
        ExtractSettings(av_engine="clamav", av_command="clamscan {path}", strict_zip_validation=True),
    )
    assert result.outcome == "error"
    assert result.preview is None
    assert result.extracted_file is not None
    assert result.av["status"] == "malicious"
    assert result.policy["decision"] == "reject"
