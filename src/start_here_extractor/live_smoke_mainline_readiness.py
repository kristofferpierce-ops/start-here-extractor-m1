from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


LIVE_SMOKE_MAINLINE_READINESS_VERSION = "1"


@dataclass(slots=True)
class LiveSmokeArtifactRef:
    name: str
    path: str | None
    present: bool
    version: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LiveSmokeMainlineReadiness:
    version: str
    promotion_target: str
    decision: str
    merge_ready: bool
    mainline_eligible: bool
    mainline_ready: bool
    on_main_branch: bool
    main_branch_ref: str
    github_ref: str | None = None
    github_sha: str | None = None
    github_event_name: str | None = None
    mainline_ack_required: bool = False
    mainline_ack_expected: str | None = None
    mainline_ack_valid: bool = True
    matrix_summary_present: bool = False
    release_gate_present: bool = False
    runbook_present: bool = False
    checklist_present: bool = False
    matrix_gate_passed: bool = False
    release_gate_decision: str | None = None
    release_gate_promote: bool = False
    manual_review_required: bool = False
    providers: list[str] = field(default_factory=list)
    required_providers: list[str] = field(default_factory=list)
    successful_providers: list[str] = field(default_factory=list)
    failed_required_providers: list[str] = field(default_factory=list)
    failed_optional_providers: list[str] = field(default_factory=list)
    invalid_contract_providers: list[str] = field(default_factory=list)
    unexpected_providers: list[str] = field(default_factory=list)
    artifacts: list[LiveSmokeArtifactRef] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    operator_actions: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        return payload


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


def _artifact_ref(name: str, path: str | Path | None, payload: dict[str, Any] | None = None, *, notes: list[str] | None = None) -> LiveSmokeArtifactRef:
    path_text = str(path) if path is not None else None
    return LiveSmokeArtifactRef(
        name=name,
        path=path_text,
        present=bool(path_text and Path(path_text).exists()),
        version=str((payload or {}).get("version") or "") or None,
        notes=_unique(list(notes or [])),
    )


def _base_operator_actions() -> list[str]:
    return [
        "Inspect the normalized release bundle before merging or promoting from hosted smoke results.",
        "Use the checked-in live smoke operator runbook for provider-specific remediation instead of copying raw workflow logs into tickets or summaries.",
        "Review the M5B closeout checklist before promoting a mainline release candidate.",
    ]


def build_live_smoke_mainline_readiness(
    *,
    matrix_summary: dict[str, Any] | None = None,
    matrix_summary_path: str | Path | None = None,
    release_gate: dict[str, Any] | None = None,
    release_gate_path: str | Path | None = None,
    promotion_target: str | None = None,
    runbook_path: str | Path | None = "LIVE_SMOKE_OPERATOR_RUNBOOK.md",
    checklist_path: str | Path | None = "MILESTONE_5B_CLOSEOUT_CHECKLIST.md",
    github_ref: str | None = None,
    github_sha: str | None = None,
    github_event_name: str | None = None,
    main_branch_ref: str = "refs/heads/main",
    mainline_ack: str | None = None,
    required_mainline_ack: str = "PROMOTE_MAIN",
) -> LiveSmokeMainlineReadiness:
    matrix_payload = dict(matrix_summary or {})
    if not matrix_payload:
        matrix_payload = _read_json(matrix_summary_path)

    release_payload = dict(release_gate or {})
    if not release_payload:
        release_payload = _read_json(release_gate_path)

    matrix_path_text = str(matrix_summary_path) if matrix_summary_path is not None else None
    release_path_text = str(release_gate_path) if release_gate_path is not None else None
    runbook_path_text = str(runbook_path) if runbook_path is not None else None
    checklist_path_text = str(checklist_path) if checklist_path is not None else None

    on_main_branch = bool(github_ref and github_ref == main_branch_ref)
    mainline_ack_required = on_main_branch
    mainline_ack_valid = not on_main_branch or str(mainline_ack or "").strip() == required_mainline_ack

    runbook_present = bool(runbook_path_text and Path(runbook_path_text).exists())
    checklist_present = bool(checklist_path_text and Path(checklist_path_text).exists())

    release_operator_actions = [str(value) for value in (release_payload.get("operator_actions") or []) if str(value).strip()]
    operator_actions = _base_operator_actions() + release_operator_actions
    reasons: list[str] = []
    notes: list[str] = []

    matrix_summary_present = bool(matrix_payload)
    release_gate_present = bool(release_payload)
    if not matrix_summary_present:
        reasons.append("Hosted smoke matrix summary artifact is missing or unreadable.")
    if not release_gate_present:
        reasons.append("Hosted smoke release gate artifact is missing or unreadable.")
    if not runbook_present:
        reasons.append("The live smoke operator runbook is missing from the repository checkout.")
    if not checklist_present:
        reasons.append("The M5B closeout checklist is missing from the repository checkout.")

    providers = [str(value) for value in (release_payload.get("providers") or matrix_payload.get("providers") or []) if str(value).strip()]
    required_providers = [str(value) for value in (release_payload.get("required_providers") or matrix_payload.get("required_providers") or []) if str(value).strip()]
    successful_providers = [str(value) for value in (release_payload.get("successful_providers") or matrix_payload.get("successful_providers") or []) if str(value).strip()]
    failed_required_providers = [str(value) for value in (release_payload.get("failed_required_providers") or []) if str(value).strip()]
    failed_optional_providers = [str(value) for value in (release_payload.get("failed_optional_providers") or []) if str(value).strip()]
    invalid_contract_providers = [str(value) for value in (release_payload.get("invalid_contract_providers") or matrix_payload.get("invalid_contract_providers") or []) if str(value).strip()]
    unexpected_providers = [str(value) for value in (release_payload.get("unexpected_providers") or matrix_payload.get("unexpected_providers") or []) if str(value).strip()]

    reasons.extend(str(value) for value in (release_payload.get("reasons") or []) if str(value).strip())
    notes.extend(str(value) for value in (release_payload.get("notes") or []) if str(value).strip())
    notes.extend(str(value) for value in (matrix_payload.get("notes") or []) if str(value).strip())

    matrix_gate_passed = bool(release_payload.get("matrix_gate_passed", matrix_payload.get("gate_passed")))
    release_gate_promote = bool(release_payload.get("promote"))
    release_gate_decision = str(release_payload.get("decision") or "") or None
    manual_review_required = bool(release_payload.get("manual_review_required"))

    merge_ready = matrix_summary_present and release_gate_present and runbook_present and checklist_present and release_gate_promote
    mainline_eligible = merge_ready and not manual_review_required and not failed_optional_providers
    if failed_optional_providers:
        reasons.append(f"Optional provider failures must be cleared before promoting on main: {', '.join(failed_optional_providers)}.")
        operator_actions.append(
            f"Resolve or consciously rerun the optional provider smoke failures before promoting on main: {', '.join(failed_optional_providers)}."
        )
    if on_main_branch and not mainline_ack_valid:
        reasons.append("Mainline promotion acknowledgement is missing or invalid for a main-branch run.")
        operator_actions.append(
            f"Rerun the main-branch smoke workflow with mainline acknowledgement set to {required_mainline_ack} after reviewing the release artifacts."
        )
    if not on_main_branch and merge_ready:
        if mainline_eligible:
            notes.append("This branch run produced a mainline-ready artifact set before merge.")
        else:
            notes.append("This branch run is merge-ready but still requires manual review before mainline promotion.")
    if on_main_branch and mainline_eligible and mainline_ack_valid:
        notes.append("Main-branch guardrails satisfied for promotion readiness.")

    mainline_ready = mainline_eligible and mainline_ack_valid
    if not merge_ready:
        decision = "hold"
    elif on_main_branch and not mainline_ready:
        decision = "hold"
    elif mainline_ready:
        decision = "ready-for-main"
    else:
        decision = "ready-for-review"

    artifacts = [
        _artifact_ref("matrix_summary", matrix_path_text, matrix_payload),
        _artifact_ref("release_gate", release_path_text, release_payload),
        _artifact_ref("runbook", runbook_path_text),
        _artifact_ref("closeout_checklist", checklist_path_text),
    ]

    promotion_target_value = str(promotion_target or release_payload.get("promotion_target") or "hosted-live-smoke-release").strip() or "hosted-live-smoke-release"

    return LiveSmokeMainlineReadiness(
        version=LIVE_SMOKE_MAINLINE_READINESS_VERSION,
        promotion_target=promotion_target_value,
        decision=decision,
        merge_ready=merge_ready,
        mainline_eligible=mainline_eligible,
        mainline_ready=mainline_ready,
        on_main_branch=on_main_branch,
        main_branch_ref=main_branch_ref,
        github_ref=str(github_ref) if github_ref is not None else None,
        github_sha=str(github_sha) if github_sha is not None else None,
        github_event_name=str(github_event_name) if github_event_name is not None else None,
        mainline_ack_required=mainline_ack_required,
        mainline_ack_expected=required_mainline_ack if mainline_ack_required else None,
        mainline_ack_valid=mainline_ack_valid,
        matrix_summary_present=matrix_summary_present,
        release_gate_present=release_gate_present,
        runbook_present=runbook_present,
        checklist_present=checklist_present,
        matrix_gate_passed=matrix_gate_passed,
        release_gate_decision=release_gate_decision,
        release_gate_promote=release_gate_promote,
        manual_review_required=manual_review_required,
        providers=providers,
        required_providers=required_providers,
        successful_providers=successful_providers,
        failed_required_providers=failed_required_providers,
        failed_optional_providers=failed_optional_providers,
        invalid_contract_providers=invalid_contract_providers,
        unexpected_providers=unexpected_providers,
        artifacts=artifacts,
        reasons=_unique(reasons),
        operator_actions=_unique(operator_actions),
        notes=_unique(notes),
    )


def build_live_smoke_release_bundle(readiness: LiveSmokeMainlineReadiness) -> dict[str, Any]:
    artifact_map = {artifact.name: artifact.to_dict() for artifact in readiness.artifacts}
    return {
        "version": LIVE_SMOKE_MAINLINE_READINESS_VERSION,
        "promotion_target": readiness.promotion_target,
        "github": {
            "ref": readiness.github_ref,
            "sha": readiness.github_sha,
            "event_name": readiness.github_event_name,
            "on_main_branch": readiness.on_main_branch,
            "main_branch_ref": readiness.main_branch_ref,
        },
        "artifacts": artifact_map,
        "status": {
            "decision": readiness.decision,
            "merge_ready": readiness.merge_ready,
            "mainline_eligible": readiness.mainline_eligible,
            "mainline_ready": readiness.mainline_ready,
            "mainline_ack_required": readiness.mainline_ack_required,
            "mainline_ack_expected": readiness.mainline_ack_expected,
            "mainline_ack_valid": readiness.mainline_ack_valid,
            "release_gate_decision": readiness.release_gate_decision,
            "release_gate_promote": readiness.release_gate_promote,
            "matrix_gate_passed": readiness.matrix_gate_passed,
            "manual_review_required": readiness.manual_review_required,
        },
        "providers": {
            "selected": list(readiness.providers),
            "required": list(readiness.required_providers),
            "successful": list(readiness.successful_providers),
            "failed_required": list(readiness.failed_required_providers),
            "failed_optional": list(readiness.failed_optional_providers),
            "invalid_contract": list(readiness.invalid_contract_providers),
            "unexpected": list(readiness.unexpected_providers),
        },
        "reasons": list(readiness.reasons),
        "operator_actions": list(readiness.operator_actions),
        "notes": list(readiness.notes),
    }


def render_live_smoke_mainline_markdown(readiness: LiveSmokeMainlineReadiness) -> str:
    lines = [
        "# Live smoke mainline readiness",
        "",
        f"- Version: `{readiness.version}`",
        f"- Promotion target: `{readiness.promotion_target}`",
        f"- Decision: `{readiness.decision}`",
        f"- Merge ready: `{'true' if readiness.merge_ready else 'false'}`",
        f"- Mainline eligible: `{'true' if readiness.mainline_eligible else 'false'}`",
        f"- Mainline ready: `{'true' if readiness.mainline_ready else 'false'}`",
        f"- On main branch: `{'true' if readiness.on_main_branch else 'false'}`",
        f"- Main branch ref: `{readiness.main_branch_ref}`",
        f"- Mainline acknowledgement required: `{'true' if readiness.mainline_ack_required else 'false'}`",
        f"- Mainline acknowledgement valid: `{'true' if readiness.mainline_ack_valid else 'false'}`",
        f"- Matrix gate passed: `{'true' if readiness.matrix_gate_passed else 'false'}`",
        f"- Release gate decision: `{readiness.release_gate_decision or 'none'}`",
        f"- Release gate promote: `{'true' if readiness.release_gate_promote else 'false'}`",
        f"- Manual review required: `{'true' if readiness.manual_review_required else 'false'}`",
        f"- Required providers: `{', '.join(readiness.required_providers) if readiness.required_providers else 'none'}`",
        f"- Successful providers: `{', '.join(readiness.successful_providers) if readiness.successful_providers else 'none'}`",
        f"- Failed required providers: `{', '.join(readiness.failed_required_providers) if readiness.failed_required_providers else 'none'}`",
        f"- Failed optional providers: `{', '.join(readiness.failed_optional_providers) if readiness.failed_optional_providers else 'none'}`",
        "",
        "## Normalized artifacts",
        "",
    ]
    for artifact in readiness.artifacts:
        lines.append(
            f"- `{artifact.name}`: present=`{'true' if artifact.present else 'false'}` path=`{artifact.path or 'none'}` version=`{artifact.version or 'none'}`"
        )
    lines.append("")
    if readiness.reasons:
        lines.append("## Reasons")
        lines.append("")
        lines.extend(f"- {reason}" for reason in readiness.reasons)
        lines.append("")
    if readiness.operator_actions:
        lines.append("## Operator actions")
        lines.append("")
        lines.extend(f"- {action}" for action in readiness.operator_actions)
        lines.append("")
    if readiness.notes:
        lines.append("## Notes")
        lines.append("")
        lines.extend(f"- {note}" for note in readiness.notes)
        lines.append("")
    return "\n".join(lines)
