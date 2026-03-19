from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MALICIOUS_PATTERNS = (
    re.compile(r"\b(infected|malicious|threat|virus found|found\s+[0-9]+\s+infected|found)\b", re.I),
    re.compile(r"\b(matches?)\b", re.I),
)


@dataclass(slots=True)
class ScanConfig:
    av_engine: str = "generic"
    av_command: str | None = None
    yara_command: str | None = None
    yara_rules: str | None = None
    yara_ruleset_id: str | None = None
    yara_compiled_rules: bool = False
    yara_allow_compiled_rules: bool = False
    timeout_seconds: int = 60


def _extract_findings(text: str) -> list[str]:
    findings: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if any(p.search(clean) for p in MALICIOUS_PATTERNS):
            findings.append(clean)
    return findings


def _run_command(command: str, *, timeout_seconds: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "error",
            "exit_code": None,
            "stdout": (exc.stdout or "")[-4000:],
            "stderr": (exc.stderr or "")[-4000:],
            "error": f"TimeoutExpired: {exc}",
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "status": "error",
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "error": f"{type(exc).__name__}: {exc}",
        }

    return {
        "status": "completed",
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def run_av_scan(path: Path, cfg: ScanConfig) -> dict[str, Any]:
    if not cfg.av_command:
        return {"engine": cfg.av_engine, "status": "not-run", "exit_code": None, "findings": []}

    command = cfg.av_command.format(path=str(path))
    raw = _run_command(command, timeout_seconds=cfg.timeout_seconds)
    stdout = str(raw.get("stdout") or "")
    stderr = str(raw.get("stderr") or "")
    exit_code = raw.get("exit_code")
    combined = "\n".join([stdout, stderr]).strip()
    findings = _extract_findings(combined)

    if raw["status"] == "error":
        return {
            "engine": cfg.av_engine,
            "status": "error",
            "exit_code": exit_code,
            "findings": findings,
            "error": raw.get("error"),
            "command": command,
        }

    engine = cfg.av_engine.lower()
    status = "clean"
    if engine == "clamav":
        if exit_code == 0:
            status = "clean"
        elif exit_code == 1:
            status = "infected"
        else:
            status = "error"
    else:
        if findings:
            status = "infected"
        elif exit_code == 0:
            status = "clean"
        else:
            status = "error"

    return {
        "engine": cfg.av_engine,
        "status": status,
        "exit_code": exit_code,
        "findings": findings,
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
    }


def run_yara_scan(path: Path, cfg: ScanConfig) -> dict[str, Any]:
    if not cfg.yara_command:
        return {
            "ruleset_id": cfg.yara_ruleset_id,
            "status": "not-run",
            "matches": [],
            "compiled_rules": bool(cfg.yara_compiled_rules),
        }

    if cfg.yara_compiled_rules and not cfg.yara_allow_compiled_rules:
        return {
            "ruleset_id": cfg.yara_ruleset_id,
            "status": "blocked",
            "matches": [],
            "compiled_rules": True,
            "reason": "compiled-rules-disallowed",
        }

    compiled_flag = "-C" if cfg.yara_compiled_rules else ""
    command = cfg.yara_command.format(
        path=str(path),
        rules=str(cfg.yara_rules or ""),
        compiled_flag=compiled_flag,
    )
    raw = _run_command(command, timeout_seconds=cfg.timeout_seconds)
    stdout = str(raw.get("stdout") or "")
    stderr = str(raw.get("stderr") or "")
    matches = [line.strip() for line in stdout.splitlines() if line.strip()]

    if raw["status"] == "error":
        return {
            "ruleset_id": cfg.yara_ruleset_id,
            "status": "error",
            "matches": matches,
            "compiled_rules": bool(cfg.yara_compiled_rules),
            "error": raw.get("error"),
            "command": command,
        }

    status = "match" if matches else "clean"
    if raw.get("exit_code") not in (0, None) and not matches:
        status = "error"

    return {
        "ruleset_id": cfg.yara_ruleset_id,
        "status": status,
        "matches": matches,
        "compiled_rules": bool(cfg.yara_compiled_rules),
        "exit_code": raw.get("exit_code"),
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
    }


def _combine_findings(av: dict[str, Any], yara: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    findings.extend(str(item) for item in av.get("findings") or [])
    findings.extend(str(item) for item in yara.get("matches") or [])
    return findings


def aggregate_scan_results(av: dict[str, Any], yara: dict[str, Any]) -> dict[str, Any]:
    av_status = str(av.get("status") or "not-run").lower()
    yara_status = str(yara.get("status") or "not-run").lower()

    overall_status = "not-run"
    if av_status in {"infected", "malicious"} or yara_status in {"match", "matched", "malicious"}:
        overall_status = "malicious"
    elif av_status in {"error", "blocked"} or yara_status in {"error", "blocked"}:
        overall_status = "inconclusive"
    elif av_status == "clean" or yara_status == "clean":
        overall_status = "clean"

    engine = av.get("engine")
    exit_code = av.get("exit_code")
    findings = _combine_findings(av, yara)
    return {
        "status": overall_status,
        "engine": engine,
        "exit_code": exit_code,
        "findings": findings,
        "av": av,
        "yara": yara,
    }


def scan_extracted_path(path: Path, cfg: ScanConfig) -> dict[str, Any]:
    av = run_av_scan(path, cfg)
    yara = run_yara_scan(path, cfg)
    return aggregate_scan_results(av, yara)
