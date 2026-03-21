from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


SUPPORTED_LIVE_SMOKE_PROVIDERS = ("gdrive", "dropbox", "graph")
LIVE_SMOKE_MATRIX_SUMMARY_VERSION = "1"


@dataclass(slots=True)
class LiveSmokeMatrixPlan:
    version: str
    providers: list[str]
    required_providers: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LiveSmokeProviderResult:
    provider: str
    expected: bool = True
    artifact_dir: str | None = None
    summary_path: str | None = None
    contract_path: str | None = None
    summary_present: bool = False
    contract_present: bool = False
    contract_valid: bool | None = None
    success: bool = False
    classification: str | None = None
    cli_exit_code: int | None = None
    reason: str | None = None
    missing_required: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LiveSmokeMatrixSummary:
    version: str
    artifact_root: str | None
    providers: list[str]
    required_providers: list[str]
    gate_passed: bool
    successful_providers: list[str] = field(default_factory=list)
    failed_providers: list[str] = field(default_factory=list)
    missing_providers: list[str] = field(default_factory=list)
    invalid_contract_providers: list[str] = field(default_factory=list)
    unexpected_providers: list[str] = field(default_factory=list)
    provider_results: list[LiveSmokeProviderResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provider_results"] = [result.to_dict() for result in self.provider_results]
        return payload


def _tokenize_provider_spec(value: str | None) -> list[str]:
    if value is None:
        return []
    normalized = str(value).replace("\n", ",").replace(";", ",")
    tokens: list[str] = []
    for chunk in normalized.split(","):
        token = chunk.strip().lower()
        if token:
            tokens.append(token)
    return tokens


def normalize_provider_selection(value: str | None, *, default_all: bool) -> list[str]:
    tokens = _tokenize_provider_spec(value)
    if not tokens:
        return list(SUPPORTED_LIVE_SMOKE_PROVIDERS) if default_all else []
    if any(token == "all" for token in tokens):
        return list(SUPPORTED_LIVE_SMOKE_PROVIDERS)
    providers: list[str] = []
    invalid: list[str] = []
    for token in tokens:
        if token not in SUPPORTED_LIVE_SMOKE_PROVIDERS:
            invalid.append(token)
            continue
        if token not in providers:
            providers.append(token)
    if invalid:
        supported = ", ".join(SUPPORTED_LIVE_SMOKE_PROVIDERS)
        invalid_text = ", ".join(invalid)
        raise ValueError(f"unsupported live smoke provider(s): {invalid_text}; supported providers: {supported}")
    return providers


def build_live_smoke_matrix_plan(providers_spec: str | None, required_providers_spec: str | None = None) -> LiveSmokeMatrixPlan:
    providers = normalize_provider_selection(providers_spec, default_all=True)
    required_providers = normalize_provider_selection(required_providers_spec, default_all=False)
    if not required_providers:
        required_providers = list(providers)
    unexpected_required = [provider for provider in required_providers if provider not in providers]
    if unexpected_required:
        unexpected_text = ", ".join(unexpected_required)
        raise ValueError(f"required provider(s) not selected for the smoke matrix: {unexpected_text}")
    return LiveSmokeMatrixPlan(
        version=LIVE_SMOKE_MATRIX_SUMMARY_VERSION,
        providers=providers,
        required_providers=required_providers,
    )


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _all_summary_paths(artifacts_root: str | Path | None) -> list[Path]:
    if not artifacts_root:
        return []
    root = Path(artifacts_root)
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("live_smoke_summary.json") if path.is_file())


def _candidate_summary_path(artifacts_root: str | Path | None, provider: str) -> Path | None:
    for path in _all_summary_paths(artifacts_root):
        marker = f"live-smoke-{provider}"
        if marker in {part.lower() for part in path.parts}:
            return path
    for path in _all_summary_paths(artifacts_root):
        payload = _read_json(path)
        if str(payload.get("provider") or "").strip().lower() == provider:
            return path
    return None


def _candidate_contract_path(summary_path: Path | None) -> Path | None:
    if summary_path is None:
        return None
    candidate = summary_path.with_name("live_smoke_artifact_contract.json")
    return candidate if candidate.exists() else None


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in result:
            result.append(item)
    return result


def _provider_result_from_artifacts(provider: str, artifacts_root: str | Path | None, *, expected: bool) -> LiveSmokeProviderResult:
    summary_path = _candidate_summary_path(artifacts_root, provider)
    contract_path = _candidate_contract_path(summary_path)
    summary_payload = _read_json(summary_path)
    contract_payload = _read_json(contract_path)
    notes = _unique(summary_payload.get("notes") or [])
    result = LiveSmokeProviderResult(
        provider=provider,
        expected=expected,
        artifact_dir=str(summary_path.parent) if summary_path else None,
        summary_path=str(summary_path) if summary_path else None,
        contract_path=str(contract_path) if contract_path else None,
        summary_present=summary_path is not None,
        contract_present=contract_path is not None,
        contract_valid=bool(contract_payload.get("valid")) if contract_payload else None,
        success=bool(summary_payload.get("success")) if summary_payload else False,
        classification=str(summary_payload.get("classification") or "") or None,
        cli_exit_code=int(summary_payload.get("cli_exit_code")) if isinstance(summary_payload.get("cli_exit_code"), int) else None,
        reason=str(summary_payload.get("reason") or "") or None,
        missing_required=[str(value) for value in (contract_payload.get("missing_required") or [])],
        notes=notes,
    )
    if not result.summary_present:
        result.reason = result.reason or "No hosted smoke artifact summary was found for the provider."
    elif not result.contract_present:
        result.reason = result.reason or "Hosted smoke artifact contract was not produced for the provider."
    elif result.contract_valid is False and not result.reason:
        result.reason = "Hosted smoke artifact contract is invalid for the provider."
    return result


def build_live_smoke_matrix_summary(
    *,
    artifacts_root: str | Path | None,
    providers: list[str],
    required_providers: list[str],
) -> LiveSmokeMatrixSummary:
    results = [_provider_result_from_artifacts(provider, artifacts_root, expected=True) for provider in providers]

    unexpected_providers: list[str] = []
    for summary_path in _all_summary_paths(artifacts_root):
        payload = _read_json(summary_path)
        provider = str(payload.get("provider") or "").strip().lower()
        if provider and provider not in providers and provider not in unexpected_providers:
            unexpected_providers.append(provider)
            results.append(_provider_result_from_artifacts(provider, artifacts_root, expected=False))

    successful_providers: list[str] = []
    failed_providers: list[str] = []
    missing_providers: list[str] = []
    invalid_contract_providers: list[str] = []
    notes: list[str] = []

    for result in results:
        if result.summary_present and result.contract_present and result.contract_valid and result.success:
            successful_providers.append(result.provider)
        elif result.expected:
            failed_providers.append(result.provider)
        if result.expected and not result.summary_present:
            missing_providers.append(result.provider)
        if result.expected and result.contract_present and result.contract_valid is False:
            invalid_contract_providers.append(result.provider)
        if result.expected and result.missing_required:
            notes.append(f"{result.provider}: missing required artifacts {', '.join(result.missing_required)}")
        if not result.expected:
            notes.append(f"unexpected provider artifact discovered for {result.provider}")

    required_failures = [
        result.provider
        for result in results
        if result.provider in required_providers and not (result.summary_present and result.contract_present and result.contract_valid and result.success)
    ]
    if required_failures:
        notes.append(f"required providers failed gate: {', '.join(required_failures)}")

    return LiveSmokeMatrixSummary(
        version=LIVE_SMOKE_MATRIX_SUMMARY_VERSION,
        artifact_root=str(artifacts_root) if artifacts_root is not None else None,
        providers=list(providers),
        required_providers=list(required_providers),
        gate_passed=not required_failures,
        successful_providers=successful_providers,
        failed_providers=failed_providers,
        missing_providers=missing_providers,
        invalid_contract_providers=invalid_contract_providers,
        unexpected_providers=unexpected_providers,
        provider_results=results,
        notes=_unique(notes),
    )


def render_live_smoke_matrix_markdown(summary: LiveSmokeMatrixSummary) -> str:
    lines = [
        "# Live smoke matrix summary",
        "",
        f"- Version: `{summary.version}`",
        f"- Gate passed: `{'true' if summary.gate_passed else 'false'}`",
        f"- Selected providers: `{', '.join(summary.providers)}`",
        f"- Required providers: `{', '.join(summary.required_providers)}`",
        f"- Successful providers: `{', '.join(summary.successful_providers) if summary.successful_providers else 'none'}`",
        f"- Failed providers: `{', '.join(summary.failed_providers) if summary.failed_providers else 'none'}`",
        f"- Missing providers: `{', '.join(summary.missing_providers) if summary.missing_providers else 'none'}`",
        f"- Invalid contracts: `{', '.join(summary.invalid_contract_providers) if summary.invalid_contract_providers else 'none'}`",
        f"- Unexpected providers: `{', '.join(summary.unexpected_providers) if summary.unexpected_providers else 'none'}`",
        "",
        "## Provider results",
    ]
    for result in summary.provider_results:
        status = "passed" if (result.summary_present and result.contract_present and result.contract_valid and result.success) else "failed"
        lines.extend(
            [
                f"- Provider: `{result.provider}`",
                f"  - Expected: `{'true' if result.expected else 'false'}`",
                f"  - Status: `{status}`",
                f"  - Summary present: `{'true' if result.summary_present else 'false'}`",
                f"  - Contract present: `{'true' if result.contract_present else 'false'}`",
                f"  - Contract valid: `{'true' if result.contract_valid else 'false' if result.contract_valid is False else 'unknown'}`",
                f"  - Success: `{'true' if result.success else 'false'}`",
            ]
        )
        optional_rows = [
            ("Classification", result.classification),
            ("CLI exit code", str(result.cli_exit_code) if result.cli_exit_code is not None else None),
            ("Reason", result.reason),
            ("Artifact directory", result.artifact_dir),
            ("Summary path", result.summary_path),
            ("Contract path", result.contract_path),
        ]
        for label, value in optional_rows:
            if value:
                lines.append(f"  - {label}: `{value}`" if label.endswith("path") or label == "Artifact directory" or label == "Classification" else f"  - {label}: {value}")
        if result.missing_required:
            lines.append("  - Missing required artifacts:")
            for item in result.missing_required:
                lines.append(f"    - `{item}`")
        if result.notes:
            lines.append("  - Notes:")
            for note in result.notes:
                lines.append(f"    - `{note}`")
    if summary.notes:
        lines.extend(["", "## Matrix notes"])
        for note in summary.notes:
            lines.append(f"- `{note}`")
    return "\n".join(lines) + "\n"
