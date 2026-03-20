from __future__ import annotations

from typing import Iterable, Mapping

from .heuristics import highest_finding_severity
from .types import PolicyDecision, StrictZipValidationResult

SANDBOX_PREFIXES = (
    "central-local-",
    "central-directory-",
    "local-header-",
    "missing-eocd",
    "truncated-eocd",
    "data-descriptor-ambiguity:",
    "duplicate-entry-name:",
)


def choose_policy_decision(
    *,
    inspection_risk_flags: Iterable[str],
    zip_hardening: StrictZipValidationResult,
    scan: Mapping[str, object] | None = None,
    sandbox_available: bool = False,
) -> PolicyDecision:
    scan = scan or {}
    av_block = scan.get("av") if isinstance(scan.get("av"), Mapping) else {}
    yara_block = scan.get("yara") if isinstance(scan.get("yara"), Mapping) else {}
    av_status = str((av_block or {}).get("status") or scan.get("status") or "not-run").lower()
    yara_status = str((yara_block or {}).get("status") or "not-run").lower()
    inspection_flags = list(inspection_risk_flags)
    hardening_flags = list(zip_hardening.flags)

    scan_findings = []
    scan_findings.extend(str(item) for item in (av_block or {}).get("findings") or [])
    scan_findings.extend(str(item) for item in (yara_block or {}).get("matches") or [])

    if av_status in {"malicious", "infected"}:
        return PolicyDecision(decision="reject", reason="av-marked-malicious", notes=scan_findings or ["scan-results"])
    if yara_status in {"match", "matched", "malicious"}:
        return PolicyDecision(decision="reject", reason="yara-match", notes=scan_findings or ["scan-results"])

    sandbox_hits = [flag for flag in hardening_flags if flag.startswith(SANDBOX_PREFIXES)]
    if sandbox_hits:
        if sandbox_available:
            return PolicyDecision(decision="sandbox", reason=sandbox_hits[0], notes=sandbox_hits)
        return PolicyDecision(decision="reject", reason="sandbox-required-but-unavailable", notes=sandbox_hits)

    if av_status in {"error", "blocked"} or yara_status in {"error", "blocked"}:
        scan_reason = str((av_block or {}).get("error") or (yara_block or {}).get("reason") or (yara_block or {}).get("error") or "scan-inconclusive")
        return PolicyDecision(decision="warn", reason=scan_reason, notes=scan_findings)

    all_flags = inspection_flags + hardening_flags
    if all_flags:
        return PolicyDecision(decision="warn", reason=all_flags[0], notes=all_flags)

    return PolicyDecision(decision="allow", reason="ok", notes=[])


def derive_governance_policy(
    *,
    operational_policy: Mapping[str, object] | None,
    heuristics_findings: list[dict] | None,
    scan: Mapping[str, object] | None,
    sandbox_available: bool,
) -> dict:
    heuristics_findings = heuristics_findings or []
    operational_policy = operational_policy or {}
    scan = scan or {}

    current_decision = str(operational_policy.get("decision") or "allow")
    current_reason = str(operational_policy.get("reason") or "ok")
    notes = [str(item) for item in (operational_policy.get("notes") or [])]

    if current_decision == "reject":
        return {
            "decision": "reject",
            "reason": current_reason,
            "notes": notes,
            "contributors": ["operational-policy"],
        }

    severity = highest_finding_severity(heuristics_findings)
    if severity in {"critical", "high"}:
        decision = "sandbox" if sandbox_available else "reject"
        return {
            "decision": decision,
            "reason": f"heuristics-{severity}",
            "notes": [str(item.get("rule_id")) for item in heuristics_findings],
            "contributors": ["heuristics"],
        }
    if severity == "medium":
        return {
            "decision": "warn",
            "reason": "heuristics-medium",
            "notes": [str(item.get("rule_id")) for item in heuristics_findings],
            "contributors": ["heuristics"],
        }

    scan_status = str(scan.get("status") or "not-run")
    if scan_status == "inconclusive":
        return {
            "decision": "warn",
            "reason": "scan-inconclusive",
            "notes": notes,
            "contributors": ["scan"],
        }

    if current_decision in {"warn", "sandbox"}:
        return {
            "decision": current_decision,
            "reason": current_reason,
            "notes": notes,
            "contributors": ["operational-policy"],
        }

    return {
        "decision": "allow",
        "reason": "ok",
        "notes": [],
        "contributors": ["summary"],
    }
