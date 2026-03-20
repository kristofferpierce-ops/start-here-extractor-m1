from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping
from uuid import uuid4

from .actions import ActionContext, ActionResult, default_registry, derive_idempotency_key
from .audit import append_audit_event, has_successful_action
from .authz import build_principal, require_action
from .errors import ActionExecutionError
from .security import redact_sensitive_fields


def _normalize_plan(plan: object) -> tuple[str, list[dict[str, object]]]:
    if isinstance(plan, list):
        return str(uuid4()), [dict(item) for item in plan]
    if isinstance(plan, Mapping):
        actions = plan.get("actions")
        if not isinstance(actions, list):
            raise ActionExecutionError("playbook plan must contain an actions list")
        return str(plan.get("plan_id") or uuid4()), [dict(item) for item in actions]
    raise ActionExecutionError("unsupported playbook plan shape")


class PlaybookRunner:
    def __init__(self, *, audit_dir: Path, durable_audit: bool = False, stream_name: str = "action-events", registry=None) -> None:
        self.audit_dir = audit_dir
        self.durable_audit = durable_audit
        self.stream_name = stream_name
        self.registry = registry or default_registry()
        self.audit_path = audit_dir / f"{stream_name}.jsonl"

    def run_playbook(
        self,
        plan: object,
        *,
        actor_id: str,
        roles: Iterable[str],
        workspace_root: str | Path,
        evidence_ref: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, object]:
        playbook_id, actions = _normalize_plan(plan)
        principal = build_principal(actor_id, roles)
        required = "playbook.run.dry_run" if dry_run else "playbook.run"
        require_action(principal, required)

        workspace = Path(workspace_root)
        workspace.mkdir(parents=True, exist_ok=True)
        start_ref = append_audit_event(
            {
                "event_type": "playbook-started",
                "playbook_id": playbook_id,
                "actor_id": principal.actor_id,
                "roles": principal.roles,
                "evidence_ref": evidence_ref,
                "dry_run": dry_run,
                "action_count": len(actions),
            },
            self.audit_dir,
            durable=self.durable_audit,
            stream_name=self.stream_name,
        )

        results: list[dict[str, object]] = []
        action_audit_refs: list[str] = []
        failures: list[dict[str, object]] = []

        for idx, raw_action in enumerate(actions, start=1):
            action_id = str(raw_action.get("id") or f"action-{idx}")
            action_type = str(raw_action.get("type") or "")
            params = dict(raw_action.get("params") or {})
            if not action_type:
                raise ActionExecutionError(f"missing-action-type:{action_id}")
            idem = str(raw_action.get("idempotency_key") or derive_idempotency_key(
                playbook_id=playbook_id,
                action_id=action_id,
                action_type=action_type,
                params=params,
                evidence_ref=evidence_ref,
            ))
            if has_successful_action(self.audit_path, idem):
                result = ActionResult(action_id, action_type, "skipped", {"reason": "idempotent-skip"}, idem)
                action_audit_refs.append(append_audit_event(
                    {
                        "event_type": "playbook-action-finished",
                        "playbook_id": playbook_id,
                        "action_id": action_id,
                        "action_type": action_type,
                        "idempotency_key": idem,
                        "actor_id": principal.actor_id,
                        "dry_run": dry_run,
                        "result": "skipped",
                        "details": result.details,
                    },
                    self.audit_dir,
                    durable=self.durable_audit,
                    stream_name=self.stream_name,
                ))
                results.append(result.to_dict())
                continue

            append_audit_event(
                {
                    "event_type": "playbook-action-started",
                    "playbook_id": playbook_id,
                    "action_id": action_id,
                    "action_type": action_type,
                    "idempotency_key": idem,
                    "actor_id": principal.actor_id,
                    "dry_run": dry_run,
                    "evidence_ref": evidence_ref,
                },
                self.audit_dir,
                durable=self.durable_audit,
                stream_name=self.stream_name,
            )

            ctx = ActionContext(workspace_root=workspace, dry_run=dry_run, actor_id=principal.actor_id, evidence_ref=evidence_ref)
            try:
                status, details = self.registry.execute(action_type, params, ctx)
                result = ActionResult(action_id, action_type, status, details, idem)
                action_audit_refs.append(append_audit_event(
                    {
                        "event_type": "playbook-action-finished",
                        "playbook_id": playbook_id,
                        "action_id": action_id,
                        "action_type": action_type,
                        "idempotency_key": idem,
                        "actor_id": principal.actor_id,
                        "dry_run": dry_run,
                        "result": status,
                        "details": details,
                    },
                    self.audit_dir,
                    durable=self.durable_audit,
                    stream_name=self.stream_name,
                ))
                results.append(result.to_dict())
            except Exception as exc:
                failure = {
                    "action_id": action_id,
                    "action_type": action_type,
                    "error": str(exc),
                    "idempotency_key": idem,
                }
                failures.append(failure)
                action_audit_refs.append(append_audit_event(
                    {
                        "event_type": "playbook-action-finished",
                        "playbook_id": playbook_id,
                        "action_id": action_id,
                        "action_type": action_type,
                        "idempotency_key": idem,
                        "actor_id": principal.actor_id,
                        "dry_run": dry_run,
                        "result": "failed",
                        "details": {"error": str(exc)},
                    },
                    self.audit_dir,
                    durable=self.durable_audit,
                    stream_name=self.stream_name,
                ))
                break

        finish_ref = append_audit_event(
            {
                "event_type": "playbook-finished",
                "playbook_id": playbook_id,
                "actor_id": principal.actor_id,
                "dry_run": dry_run,
                "result": "failed" if failures else "completed",
                "actions_executed": len(results),
                "failures": failures,
            },
            self.audit_dir,
            durable=self.durable_audit,
            stream_name=self.stream_name,
        )

        output = {
            "playbook_id": playbook_id,
            "actor": principal.to_dict(),
            "dry_run": dry_run,
            "evidence_ref": evidence_ref,
            "workspace_root": str(workspace.resolve()),
            "start_audit_ref": start_ref,
            "finish_audit_ref": finish_ref,
            "action_audit_refs": action_audit_refs,
            "playbook_actions": results,
            "authorization_decision": {
                "required_action": required,
                "decision": "allow",
                "actor_id": principal.actor_id,
                "roles": principal.roles,
            },
            "status": "failed" if failures else "completed",
            "failures": failures,
        }
        return redact_sensitive_fields(output)


def load_playbook(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))
