from __future__ import annotations

import json
from pathlib import Path

import pytest

from start_here_extractor.audit import count_audit_records, iter_audit_records
from start_here_extractor.errors import AuthorizationError
from start_here_extractor.playbooks import PlaybookRunner
from start_here_extractor.playbooks_cli import main as playbook_main


def sample_plan() -> dict:
    return {
        "plan_id": "demo-plan",
        "actions": [
            {"id": "write-note", "type": "write-file", "params": {"path": "notes/result.txt", "content": "hello"}},
            {"id": "marker", "type": "touch-marker", "params": {"path": "markers/done.txt"}},
        ],
    }


def test_playbook_dry_run_does_not_mutate_workspace(tmp_path: Path):
    runner = PlaybookRunner(audit_dir=tmp_path / "audit")
    result = runner.run_playbook(sample_plan(), actor_id="analyst-1", roles=["analyst"], workspace_root=tmp_path / "ws", dry_run=True)
    assert result["status"] == "completed"
    assert (tmp_path / "ws" / "notes" / "result.txt").exists() is False
    assert result["playbook_actions"][0]["status"] == "planned"


def test_playbook_denies_live_run_without_permission(tmp_path: Path):
    runner = PlaybookRunner(audit_dir=tmp_path / "audit")
    with pytest.raises(AuthorizationError):
        runner.run_playbook(sample_plan(), actor_id="analyst-1", roles=["analyst"], workspace_root=tmp_path / "ws", dry_run=False)


def test_playbook_idempotency_skips_second_run(tmp_path: Path):
    runner = PlaybookRunner(audit_dir=tmp_path / "audit")
    first = runner.run_playbook(sample_plan(), actor_id="operator-1", roles=["operator"], workspace_root=tmp_path / "ws", dry_run=False)
    second = runner.run_playbook(sample_plan(), actor_id="operator-1", roles=["operator"], workspace_root=tmp_path / "ws", dry_run=False)
    assert first["status"] == "completed"
    assert second["playbook_actions"][0]["status"] == "skipped"
    assert (tmp_path / "ws" / "notes" / "result.txt").read_text(encoding="utf-8") == "hello"


def test_action_audit_records_are_appended(tmp_path: Path):
    audit_dir = tmp_path / "audit"
    runner = PlaybookRunner(audit_dir=audit_dir, stream_name="action-events")
    result = runner.run_playbook(sample_plan(), actor_id="operator-1", roles=["operator"], workspace_root=tmp_path / "ws", dry_run=False)
    audit_path = audit_dir / "action-events.jsonl"
    assert count_audit_records(audit_path) >= 4
    events = list(iter_audit_records(audit_path))
    assert any(e.get("event_type") == "playbook-started" for e in events)
    assert any(e.get("event_type") == "playbook-action-finished" and e.get("result") == "applied" for e in events)
    assert result["action_audit_refs"]


def test_playbook_cli_smoke(tmp_path: Path, capsys):
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(sample_plan()), encoding="utf-8")
    rc = playbook_main([
        str(plan_path),
        "--workspace-root", str(tmp_path / "ws"),
        "--audit-dir", str(tmp_path / "audit"),
        "--actor-id", "operator-1",
        "--role", "operator",
        "--dry-run",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["authorization_decision"]["decision"] == "allow"
    assert payload["dry_run"] is True
