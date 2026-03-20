from __future__ import annotations

import re
from typing import Iterable

_RULES = [
    {
        "rule_id": "disable-av",
        "pattern": re.compile(r"\b(?:disable|turn off|bypass)\s+(?:av|antivirus|defender|security)\b", re.I),
        "category": "security-bypass",
        "severity": "critical",
        "score": 100,
        "title": "Instruction appears to disable security tooling.",
    },
    {
        "rule_id": "run-as-admin",
        "pattern": re.compile(r"\b(?:run as admin(?:istrator)?|elevated prompt|sudo)\b", re.I),
        "category": "privilege-escalation",
        "severity": "high",
        "score": 80,
        "title": "Instruction appears to request elevated privileges.",
    },
    {
        "rule_id": "curl-pipe-shell",
        "pattern": re.compile(r"(?:curl|wget)[^\n]{0,120}\|\s*(?:bash|sh)|iex\s*\(|invoke-expression", re.I),
        "category": "remote-execution",
        "severity": "critical",
        "score": 95,
        "title": "Instruction appears to download and execute a remote payload.",
    },
    {
        "rule_id": "powershell-encoded-command",
        "pattern": re.compile(r"(?:powershell|pwsh)[^\n]{0,120}-(?:enc|encodedcommand)\b", re.I),
        "category": "obfuscation",
        "severity": "high",
        "score": 85,
        "title": "Instruction appears to use an encoded PowerShell command.",
    },
    {
        "rule_id": "delete-logs",
        "pattern": re.compile(r"\b(?:clear|delete|wipe|remove)\s+(?:logs?|history|evidence)\b", re.I),
        "category": "anti-forensics",
        "severity": "high",
        "score": 75,
        "title": "Instruction appears to remove audit or forensic evidence.",
    },
]


def _excerpt(text: str, start: int, end: int, radius: int = 32) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].strip()


def detect_dangerous_instructions(text: str) -> list[dict]:
    findings: list[dict] = []
    if not text:
        return findings
    seen: set[tuple[str, int, int]] = set()
    for rule in _RULES:
        for match in rule["pattern"].finditer(text):
            key = (str(rule["rule_id"]), match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "rule_id": rule["rule_id"],
                    "category": rule["category"],
                    "severity": rule["severity"],
                    "score": rule["score"],
                    "title": rule["title"],
                    "reason": match.group(0),
                    "evidence_ref": "preview_text",
                    "excerpt": _excerpt(text, match.start(), match.end()),
                }
            )
    findings.sort(key=lambda item: (-int(item["score"]), str(item["rule_id"])))
    return findings


def highest_finding_severity(findings: Iterable[dict]) -> str | None:
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    best: tuple[int, str] | None = None
    for finding in findings:
        severity = str(finding.get("severity") or "").lower()
        score = order.get(severity)
        if score is None:
            continue
        if best is None or score > best[0]:
            best = (score, severity)
    return best[1] if best else None
