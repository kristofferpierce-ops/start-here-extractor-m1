"""Phase 19 release-checkpoint evidence indexing.

This module is intentionally read-only with respect to the platform, bridge, and
CRM systems. It consumes a Phase 19 release checkpoint JSON file and produces a
redacted evidence index for audit/replay review.

It is designed to let the extractor repo participate in the wider KPS R&D
integration as the evidence/governance subsystem rather than a business source
of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PHONE_RE = re.compile(r"(?<!\w)(?:\+?1[\s\-\.]?)?(?:\(?\d{3}\)?[\s\-\.]?)\d{3}[\s\-\.]?\d{4}(?!\w)")
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b")
TOKENISH_KEYS = {
    "api_key",
    "access_token",
    "refresh_token",
    "authorization",
    "password",
    "secret",
    "token",
    "payload_json",
    "raw_json",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def redact_text(value: str) -> str:
    value = EMAIL_RE.sub("[redacted-email]", value)
    value = PHONE_RE.sub("[redacted-phone]", value)
    return value


def redact_value(value: Any, *, key: str = "") -> Any:
    key_l = key.lower()
    if any(part in key_l for part in TOKENISH_KEYS):
        if value in (None, "", [], {}):
            return value
        return "[redacted-sensitive]"

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_value(v, key=k) for k, v in value.items()}
    return value


def dig(data: dict[str, Any], *path: str, default: Any = None) -> Any:
    cur: Any = data
    for part in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
    return cur if cur is not None else default


def summarize_checkpoint(data: dict[str, Any]) -> dict[str, Any]:
    ingestion = dig(data, "integration", "ingestion_status", default={})
    lacrm = dig(data, "lacrm_safety", "status", default={})
    readiness = dig(data, "lacrm_safety", "live_readiness", default={})
    runtime = data.get("runtime", {}) if isinstance(data.get("runtime"), dict) else {}
    git = data.get("git", {}) if isinstance(data.get("git"), dict) else {}

    platform_git = git.get("platform", {}) if isinstance(git.get("platform"), dict) else {}
    bridge_git = git.get("bridge_repo", {}) if isinstance(git.get("bridge_repo"), dict) else {}
    extractor_git = git.get("extractor", {}) if isinstance(git.get("extractor"), dict) else {}

    return {
        "checkpoint_generated_at": data.get("generated_at"),
        "phase": data.get("phase"),
        "runtime": {
            "fastapi_health_ok": bool(runtime.get("fastapi_health_ok")),
            "streamlit_reachable": bool(runtime.get("streamlit_reachable")),
            "bridge_original_data_hub": bool(runtime.get("bridge_original_data_hub")),
        },
        "integration_counts": {
            "raw_total": int(ingestion.get("raw_total") or 0),
            "sms_threads_total": int(ingestion.get("sms_threads_total") or 0),
            "sms_messages_total": int(ingestion.get("sms_messages_total") or 0),
        },
        "lacrm_safety": {
            "live_write_enabled": bool(lacrm.get("live_write_enabled")),
            "live_write_armed": bool(lacrm.get("live_write_armed")),
            "default_mode": lacrm.get("default_mode"),
            "ready_for_live_apply": bool(readiness.get("ready_for_live_apply")),
            "status_counts": lacrm.get("status_counts") if isinstance(lacrm.get("status_counts"), dict) else {},
        },
        "repo_boundaries": {
            "platform_branch": platform_git.get("branch"),
            "bridge_repo_branch": bridge_git.get("branch"),
            "extractor_branch": extractor_git.get("branch"),
            "platform_is_git_repo": bool(platform_git.get("is_git_repo")),
            "bridge_repo_is_git_repo": bool(bridge_git.get("is_git_repo")),
            "extractor_is_git_repo": bool(extractor_git.get("is_git_repo")),
        },
        "guardrails": {
            "commit_database": dig(data, "recommendation", "commit_database", default=False),
            "commit_env_files": dig(data, "recommendation", "commit_env_files", default=False),
            "live_lacrm_apply_allowed": dig(data, "recommendation", "live_lacrm_apply_allowed", default=False),
            "bridge_repo_should_remain_separate": dig(data, "recommendation", "bridge_repo_should_remain_separate", default=True),
            "blocked_patterns_visible_in_platform_status": dig(
                data, "git", "blocked_patterns_visible_in_platform_status", default=[]
            ),
        },
    }


def build_evidence_index(checkpoint_path: Path) -> dict[str, Any]:
    data = json.loads(checkpoint_path.read_text(encoding="utf-8-sig"))
    redacted = redact_value(data)
    summary = summarize_checkpoint(data)

    safety_ok = (
        summary["runtime"]["fastapi_health_ok"]
        and summary["runtime"]["streamlit_reachable"]
        and summary["runtime"]["bridge_original_data_hub"]
        and summary["integration_counts"]["sms_messages_total"] >= 1
        and not summary["lacrm_safety"]["live_write_enabled"]
        and not summary["lacrm_safety"]["live_write_armed"]
        and not summary["lacrm_safety"]["ready_for_live_apply"]
    )

    return {
        "evidence_index_version": "phase19-step16-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_checkpoint_path": str(checkpoint_path),
        "source_checkpoint_sha256": sha256_file(checkpoint_path),
        "summary": summary,
        "safety_ok": bool(safety_ok),
        "redaction": {
            "phones": "redacted",
            "emails": "redacted",
            "tokenish_fields": "redacted",
            "raw_payload_fields": "redacted",
        },
        "redacted_checkpoint": redacted,
    }


def write_evidence_pack(checkpoint_path: Path, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    index = build_evidence_index(checkpoint_path)

    index_path = out_dir / "phase19_evidence_index.json"
    summary_path = out_dir / "phase19_evidence_summary.json"
    redacted_path = out_dir / "phase19_redacted_checkpoint.json"

    index_path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    summary_path.write_text(json.dumps(index["summary"], indent=2, sort_keys=True), encoding="utf-8")
    redacted_path.write_text(json.dumps(index["redacted_checkpoint"], indent=2, sort_keys=True), encoding="utf-8")

    return {
        "index": index_path,
        "summary": summary_path,
        "redacted_checkpoint": redacted_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a redacted Phase 19 evidence index from a release checkpoint JSON.")
    parser.add_argument("--checkpoint", required=True, help="Path to phase19_release_checkpoint_*.json")
    parser.add_argument("--out-dir", required=True, help="Directory for generated evidence files")
    args = parser.parse_args(argv)

    checkpoint = Path(args.checkpoint)
    out_dir = Path(args.out_dir)

    if not checkpoint.exists():
        raise SystemExit(f"Checkpoint not found: {checkpoint}")

    paths = write_evidence_pack(checkpoint, out_dir)
    print("PASS | Phase 19 evidence pack written")
    for key, path in paths.items():
        print(f"{key}: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

