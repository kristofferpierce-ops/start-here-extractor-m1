from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .errors import ActionExecutionError, PathTraversalRisk


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def derive_idempotency_key(*, playbook_id: str, action_id: str, action_type: str, params: Mapping[str, object], evidence_ref: str | None) -> str:
    payload = {
        "playbook_id": playbook_id,
        "action_id": action_id,
        "action_type": action_type,
        "params": params,
        "evidence_ref": evidence_ref,
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def resolve_workspace_path(workspace_root: Path, relative_path: str) -> Path:
    candidate = (workspace_root / relative_path).resolve()
    root = workspace_root.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PathTraversalRisk(f"workspace-path-escape:{relative_path}") from exc
    return candidate


@dataclass(slots=True)
class ActionContext:
    workspace_root: Path
    dry_run: bool
    actor_id: str
    evidence_ref: str | None


@dataclass(slots=True)
class ActionResult:
    action_id: str
    action_type: str
    status: str
    details: dict[str, object]
    idempotency_key: str

    def to_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "status": self.status,
            "details": self.details,
            "idempotency_key": self.idempotency_key,
        }


ActionHandler = Callable[[dict[str, object], ActionContext], tuple[str, dict[str, object]]]


class ActionRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, action_type: str, handler: ActionHandler) -> None:
        self._handlers[action_type] = handler

    def get(self, action_type: str) -> ActionHandler:
        if action_type not in self._handlers:
            raise ActionExecutionError(f"unknown-action-type:{action_type}")
        return self._handlers[action_type]

    def execute(self, action_type: str, params: dict[str, object], ctx: ActionContext) -> tuple[str, dict[str, object]]:
        return self.get(action_type)(params, ctx)


def _write_file(params: dict[str, object], ctx: ActionContext) -> tuple[str, dict[str, object]]:
    rel_path = str(params.get("path") or "")
    if not rel_path:
        raise ActionExecutionError("write-file requires path")
    content = str(params.get("content") or "")
    path = resolve_workspace_path(ctx.workspace_root, rel_path)
    exists = path.exists()
    current = path.read_text(encoding="utf-8") if exists and path.is_file() else None
    if exists and current == content:
        return "already-applied", {"path": str(path), "bytes": len(content.encode("utf-8"))}
    if ctx.dry_run:
        return "planned", {"path": str(path), "bytes": len(content.encode("utf-8")), "would_overwrite": exists}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "applied", {"path": str(path), "bytes": len(content.encode("utf-8")), "overwrote": exists}


def _delete_path(params: dict[str, object], ctx: ActionContext) -> tuple[str, dict[str, object]]:
    rel_path = str(params.get("path") or "")
    if not rel_path:
        raise ActionExecutionError("delete-path requires path")
    path = resolve_workspace_path(ctx.workspace_root, rel_path)
    if not path.exists():
        return "already-applied", {"path": str(path), "missing": True}
    if ctx.dry_run:
        return "planned", {"path": str(path), "kind": "dir" if path.is_dir() else "file"}
    if path.is_dir():
        shutil.rmtree(path)
        return "applied", {"path": str(path), "kind": "dir"}
    path.unlink()
    return "applied", {"path": str(path), "kind": "file"}


def _touch_marker(params: dict[str, object], ctx: ActionContext) -> tuple[str, dict[str, object]]:
    rel_path = str(params.get("path") or "markers/marker.txt")
    path = resolve_workspace_path(ctx.workspace_root, rel_path)
    if path.exists():
        return "already-applied", {"path": str(path)}
    if ctx.dry_run:
        return "planned", {"path": str(path)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("created by playbook\n", encoding="utf-8")
    return "applied", {"path": str(path)}


def default_registry() -> ActionRegistry:
    registry = ActionRegistry()
    registry.register("write-file", _write_file)
    registry.register("delete-path", _delete_path)
    registry.register("touch-marker", _touch_marker)
    return registry
