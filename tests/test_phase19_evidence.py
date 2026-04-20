from __future__ import annotations

import json
from pathlib import Path

from start_here_extractor.phase19_evidence import build_evidence_index, redact_text, write_evidence_pack


def test_redact_text_removes_phones_and_emails() -> None:
    text = "Call +13057314448 or email owner@example.com for this checkpoint."
    redacted = redact_text(text)
    assert "+13057314448" not in redacted
    assert "owner@example.com" not in redacted
    assert "[redacted-phone]" in redacted
    assert "[redacted-email]" in redacted


def test_build_evidence_index_summarizes_and_redacts(tmp_path: Path) -> None:
    checkpoint = {
        "generated_at": "2026-04-20T00:00:00Z",
        "phase": "Phase 19 Step 15",
        "runtime": {
            "fastapi_health_ok": True,
            "streamlit_reachable": True,
            "bridge_original_data_hub": True,
        },
        "integration": {
            "ingestion_status": {
                "raw_total": 22,
                "sms_threads_total": 8,
                "sms_messages_total": 22,
                "latest_sms_threads": [
                    {
                        "external_phone": "+13057314448",
                        "transcript": "Owner owner@example.com asked for status.",
                        "raw_json": "{\"secret\":\"do-not-keep\"}",
                    }
                ],
            }
        },
        "lacrm_safety": {
            "status": {
                "live_write_enabled": False,
                "live_write_armed": False,
                "default_mode": "dry_run",
                "status_counts": {"dry_run": 2},
            },
            "live_readiness": {"ready_for_live_apply": False},
        },
        "git": {
            "platform": {"branch": "phase19-step15-release-checkpoint", "is_git_repo": True},
            "bridge_repo": {"branch": "phase19-step3-bridge-outbox", "is_git_repo": True},
            "extractor": {"branch": "phase19-step16-extractor-evidence", "is_git_repo": True},
            "blocked_patterns_visible_in_platform_status": [],
        },
        "recommendation": {
            "commit_database": False,
            "commit_env_files": False,
            "live_lacrm_apply_allowed": False,
            "bridge_repo_should_remain_separate": True,
        },
    }
    path = tmp_path / "checkpoint.json"
    path.write_text(json.dumps(checkpoint), encoding="utf-8")

    index = build_evidence_index(path)

    assert index["safety_ok"] is True
    assert index["summary"]["integration_counts"]["sms_messages_total"] == 22
    serialized = json.dumps(index)
    assert "+13057314448" not in serialized
    assert "owner@example.com" not in serialized
    assert "do-not-keep" not in serialized
    assert "[redacted-phone]" in serialized
    assert "[redacted-sensitive]" in serialized


def test_write_evidence_pack_outputs_expected_files(tmp_path: Path) -> None:
    checkpoint = {
        "generated_at": "2026-04-20T00:00:00Z",
        "phase": "Phase 19 Step 15",
        "runtime": {"fastapi_health_ok": True, "streamlit_reachable": True, "bridge_original_data_hub": True},
        "integration": {"ingestion_status": {"sms_messages_total": 1}},
        "lacrm_safety": {
            "status": {"live_write_enabled": False, "live_write_armed": False},
            "live_readiness": {"ready_for_live_apply": False},
        },
    }
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    out_dir = tmp_path / "evidence"

    paths = write_evidence_pack(checkpoint_path, out_dir)

    assert paths["index"].exists()
    assert paths["summary"].exists()
    assert paths["redacted_checkpoint"].exists()
    assert json.loads(paths["index"].read_text(encoding="utf-8"))["source_checkpoint_sha256"]

def test_build_evidence_index_accepts_utf8_bom_checkpoint(tmp_path: Path) -> None:
    checkpoint = {
        "generated_at": "2026-04-20T00:00:00Z",
        "phase": "Phase 19 Step 15",
        "runtime": {"fastapi_health_ok": True, "streamlit_reachable": True, "bridge_original_data_hub": True},
        "integration": {"ingestion_status": {"sms_messages_total": 1}},
        "lacrm_safety": {
            "status": {"live_write_enabled": False, "live_write_armed": False},
            "live_readiness": {"ready_for_live_apply": False},
        },
    }
    path = tmp_path / "checkpoint_bom.json"
    path.write_text(json.dumps(checkpoint), encoding="utf-8-sig")

    index = build_evidence_index(path)

    assert index["safety_ok"] is True
    assert index["summary"]["integration_counts"]["sms_messages_total"] == 1
