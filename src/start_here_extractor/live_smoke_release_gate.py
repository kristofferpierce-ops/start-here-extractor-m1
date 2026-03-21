from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


LIVE_SMOKE_RELEASE_GATE_VERSION = "1"


@dataclass(slots=True)
class LiveSmokeReleaseDecision:
    version: str
    promotion_target: str
    decision: str
    promote: bool
    matrix_summary_present: bool
    matrix_summary_version: str | None = None
    matrix_summary_path: str | None = None
    runbook_path: str | None = None
    runbook_present: bool = False
    matrix_gate_passed: bool = False
    providers: list[str] = field(default_factory=list)
    required_providers: list[str] = field(default_factory=list)
    successful_providers: list[str] = field(default_factory=list)
    failed_required_providers: list[str] = field(default_factory=list)
    failed_optional_providers: list[str] = field(default_factory=list)
    missing_providers: list[str] = field(default_factory=list)
    invalid_contract_providers: list[str] = field(default_factory=list)
    unexpected_providers: list[str] = field(default_factory=list)
    manual_review_required: bool = False
    reasons: list[str] = field(default_factory=list)
    operator_actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_json(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        value = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in result:
            result.append(item)
    return result


def _provider_result_map(summary_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    provider_results = summary_payload.get("provider_results") or []
    results: dict[str, dict[str, Any]] = {}
    for value in provider_results:
        if not isinstance(value, dict):
            continue
        provider = str(value.get("provider") or "").strip().lower()
        if provider and provider not in results:
            results[provider] = value
    return results


def _result_action(provider: str, result: dict[str, Any]) -> str | None:
    classification = str(result.get("classification") or "").strip().lower()
    if classification == "token-resolution-failed":
        return f"{provider}: verify the provider secret exists, the token command resolves locally, and the command emits only the token payload."
    if classification == "auth-failed":
        return f"{provider}: confirm the access token is still valid and includes the expected provider scopes before rerunning the smoke job."
    if classification == "rate-limited":
        return f"{provider}: review retry telemetry, wait for provider throttling to clear, then rerun the smoke workflow for the affected provider."
    if classification == "no-remote-zip":
        return f"{provider}: confirm the smoke query resolves to a deterministic remote ZIP in the provider test location before promoting a release."
    if not bool(result.get("summary_present")):
        return f"{provider}: verify the workflow matrix ran for the provider and that artifact download patterns still match the provider artifact name."
    if bool(result.get("contract_present")) and result.get("contract_valid") is False:
        missing = [str(item) for item in (result.get("missing_required") or []) if str(item).strip()]
        if missing:
            return f"{provider}: rebuild the hosted smoke artifact set so the required artifacts exist: {', '.join(missing)}."
        return f"{provider}: rebuild the hosted smoke artifact set and verify the contract is valid before rerunning promotion gating."
    reason = str(result.get("reason") or "").strip()
    if reason:
        return f"{provider}: {reason}"
    return None


def _base_operator_actions() -> list[str]:
    return [
        "Inspect the release decision artifact before retrying the promotion path.",
        "Use the checked-in live smoke operator runbook for the matching failure mode and rerun only the affected providers first.",
        "Do not paste raw token material into workflow summaries, logs, or decision artifacts while triaging hosted smoke failures.",
    ]


def build_live_smoke_release_decision(
    *,
    matrix_summary: dict[str, Any] | None = None,
    matrix_summary_path: str | Path | None = None,
    promotion_target: str = "hosted-live-smoke-release",
    runbook_path: str | Path | None = "LIVE_SMOKE_OPERATOR_RUNBOOK.md",
) -> LiveSmokeReleaseDecision:
    summary_payload = dict(matrix_summary or {})
    if not summary_payload:
        summary_payload = _read_json(matrix_summary_path)

    matrix_path_text = str(matrix_summary_path) if matrix_summary_path is not None else None
    runbook_path_text = str(runbook_path) if runbook_path is not None else None
    runbook_present = bool(runbook_path_text and Path(runbook_path_text).exists())

    reasons: list[str] = []
    operator_actions = _base_operator_actions()
    notes: list[str] = []

    if not summary_payload:
        reasons.append("Hosted smoke matrix summary artifact is missing or unreadable.")
        if not runbook_present:
            reasons.append("The live smoke operator runbook is missing from the repository checkout.")
        return LiveSmokeReleaseDecision(
            version=LIVE_SMOKE_RELEASE_GATE_VERSION,
            promotion_target=promotion_target,
            decision="hold",
            promote=False,
            matrix_summary_present=False,
            matrix_summary_path=matrix_path_text,
            runbook_path=runbook_path_text,
            runbook_present=runbook_present,
            manual_review_required=True,
            reasons=_unique(reasons),
            operator_actions=_unique(operator_actions),
            notes=notes,
        )

    providers = [str(value) for value in (summary_payload.get("providers") or []) if str(value).strip()]
    required_providers = [str(value) for value in (summary_payload.get("required_providers") or []) if str(value).strip()]
    successful_providers = [str(value) for value in (summary_payload.get("successful_providers") or []) if str(value).strip()]
    failed_providers = [str(value) for value in (summary_payload.get("failed_providers") or []) if str(value).strip()]
    missing_providers = [str(value) for value in (summary_payload.get("missing_providers") or []) if str(value).strip()]
    invalid_contract_providers = [str(value) for value in (summary_payload.get("invalid_contract_providers") or []) if str(value).strip()]
    unexpected_providers = [str(value) for value in (summary_payload.get("unexpected_providers") or []) if str(value).strip()]
    provider_results = _provider_result_map(summary_payload)

    failed_required_providers = [provider for provider in required_providers if provider not in successful_providers]
    failed_optional_providers = [
        provider
        for provider in failed_providers
        if provider not in required_providers
    ]

    gate_passed = bool(summary_payload.get("gate_passed"))
    if not gate_passed:
        reasons.append("Hosted smoke matrix gate did not pass for the required providers.")
    if failed_required_providers:
        reasons.append(f"Required providers failed promotion gating: {', '.join(failed_required_providers)}.")
    if invalid_contract_providers:
        reasons.append(f"Invalid hosted smoke artifact contracts were detected for: {', '.join(invalid_contract_providers)}.")
    if unexpected_providers:
        reasons.append(f"Unexpected provider artifacts were discovered: {', '.join(unexpected_providers)}.")
    if not runbook_present:
        reasons.append("The live smoke operator runbook is missing from the repository checkout.")

    for provider in failed_required_providers + invalid_contract_providers + unexpected_providers + failed_optional_providers:
        action = _result_action(provider, provider_results.get(provider, {}))
        if action:
            operator_actions.append(action)

    notes.extend([str(value) for value in (summary_payload.get("notes") or []) if str(value).strip()])

    promote = gate_passed and not invalid_contract_providers and not unexpected_providers and runbook_present
    decision = "promote" if promote else "hold"
    manual_review_required = not promote or bool(failed_optional_providers)
    if failed_optional_providers:
        notes.append(f"Optional providers failed but do not block promotion by policy: {', '.join(failed_optional_providers)}.")

    return LiveSmokeReleaseDecision(
        version=LIVE_SMOKE_RELEASE_GATE_VERSION,
        promotion_target=promotion_target,
        decision=decision,
        promote=promote,
        matrix_summary_present=True,
        matrix_summary_version=str(summary_payload.get("version") or "") or None,
        matrix_summary_path=matrix_path_text,
        runbook_path=runbook_path_text,
        runbook_present=runbook_present,
        matrix_gate_passed=gate_passed,
        providers=providers,
        required_providers=required_providers,
        successful_providers=successful_providers,
        failed_required_providers=failed_required_providers,
        failed_optional_providers=failed_optional_providers,
        missing_providers=missing_providers,
        invalid_contract_providers=invalid_contract_providers,
        unexpected_providers=unexpected_providers,
        manual_review_required=manual_review_required,
        reasons=_unique(reasons),
        operator_actions=_unique(operator_actions),
        notes=_unique(notes),
    )


def render_live_smoke_release_markdown(decision: LiveSmokeReleaseDecision) -> str:
    lines = [
        "# Live smoke release decision",
        "",
        f"- Version: `{decision.version}`",
        f"- Promotion target: `{decision.promotion_target}`",
        f"- Decision: `{decision.decision}`",
        f"- Promote: `{'true' if decision.promote else 'false'}`",
        f"- Matrix summary present: `{'true' if decision.matrix_summary_present else 'false'}`",
        f"- Matrix gate passed: `{'true' if decision.matrix_gate_passed else 'false'}`",
        f"- Runbook present: `{'true' if decision.runbook_present else 'false'}`",
        f"- Required providers: `{', '.join(decision.required_providers) if decision.required_providers else 'none'}`",
        f"- Successful providers: `{', '.join(decision.successful_providers) if decision.successful_providers else 'none'}`",
        f"- Failed required providers: `{', '.join(decision.failed_required_providers) if decision.failed_required_providers else 'none'}`",
        f"- Failed optional providers: `{', '.join(decision.failed_optional_providers) if decision.failed_optional_providers else 'none'}`",
        f"- Invalid contract providers: `{', '.join(decision.invalid_contract_providers) if decision.invalid_contract_providers else 'none'}`",
        f"- Unexpected providers: `{', '.join(decision.unexpected_providers) if decision.unexpected_providers else 'none'}`",
        f"- Runbook path: `{decision.runbook_path or 'none'}`",
        "",
    ]
    if decision.reasons:
        lines.append("## Reasons")
        lines.append("")
        lines.extend(f"- {reason}" for reason in decision.reasons)
        lines.append("")
    if decision.operator_actions:
        lines.append("## Operator actions")
        lines.append("")
        lines.extend(f"- {action}" for action in decision.operator_actions)
        lines.append("")
    if decision.notes:
        lines.append("## Notes")
        lines.append("")
        lines.extend(f"- {note}" for note in decision.notes)
        lines.append("")
    return "\n".join(lines)
