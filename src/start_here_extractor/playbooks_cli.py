from __future__ import annotations

import argparse
import json
from pathlib import Path

from .playbooks import PlaybookRunner, load_playbook


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a deterministic remediation playbook")
    parser.add_argument("plan", help="Path to a JSON playbook plan")
    parser.add_argument("--workspace-root", required=True, help="Workspace root for action paths")
    parser.add_argument("--audit-dir", required=True, help="Directory for immutable action audit JSONL")
    parser.add_argument("--actor-id", required=True, help="Actor/user identifier")
    parser.add_argument("--role", action="append", default=[], help="Role assigned to the actor")
    parser.add_argument("--dry-run", action="store_true", help="Plan actions without mutating state")
    parser.add_argument("--evidence-ref", default=None, help="Optional evidence reference linked to the playbook")
    parser.add_argument("--audit-stream-name", default="action-events", help="Action audit stream name without extension")
    parser.add_argument("--durable-audit", action="store_true", help="fsync action audit JSONL writes")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runner = PlaybookRunner(audit_dir=Path(args.audit_dir), durable_audit=bool(args.durable_audit), stream_name=args.audit_stream_name)
    plan = load_playbook(args.plan)
    result = runner.run_playbook(
        plan,
        actor_id=args.actor_id,
        roles=args.role,
        workspace_root=args.workspace_root,
        evidence_ref=args.evidence_ref,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
