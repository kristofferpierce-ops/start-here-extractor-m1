from __future__ import annotations

from typing import Iterable, Mapping

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
    av_status = str(scan.get("status") or "not-run").lower()
    inspection_flags = list(inspection_risk_flags)
    hardening_flags = list(zip_hardening.flags)

    if av_status in {"malicious", "infected"}:
        return PolicyDecision(decision="reject", reason="av-marked-malicious", notes=["scan-results"])

    sandbox_hits = [flag for flag in hardening_flags if flag.startswith(SANDBOX_PREFIXES)]
    if sandbox_hits:
        if sandbox_available:
            return PolicyDecision(decision="sandbox", reason=sandbox_hits[0], notes=sandbox_hits)
        return PolicyDecision(decision="reject", reason="sandbox-required-but-unavailable", notes=sandbox_hits)

    all_flags = inspection_flags + hardening_flags
    if all_flags:
        return PolicyDecision(decision="warn", reason=all_flags[0], notes=all_flags)

    return PolicyDecision(decision="allow", reason="ok", notes=[])
