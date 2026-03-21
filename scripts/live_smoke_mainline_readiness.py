from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.live_smoke_mainline_readiness import (
    build_live_smoke_mainline_readiness,
    build_live_smoke_release_bundle,
    render_live_smoke_mainline_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build merge-readiness and mainline-promotion artifacts from hosted smoke outputs")
    parser.add_argument("--matrix-summary", required=True, help="Path to the live smoke matrix summary JSON artifact")
    parser.add_argument("--release-gate", required=True, help="Path to the live smoke release gate JSON artifact")
    parser.add_argument("--out-dir", required=True, help="Output directory for mainline-readiness artifacts")
    parser.add_argument(
        "--promotion-target",
        default="",
        help="Optional promotion target override written into the normalized release bundle",
    )
    parser.add_argument(
        "--runbook-path",
        default="LIVE_SMOKE_OPERATOR_RUNBOOK.md",
        help="Path to the checked-in live smoke operator runbook",
    )
    parser.add_argument(
        "--checklist-path",
        default="MILESTONE_5B_CLOSEOUT_CHECKLIST.md",
        help="Path to the checked-in M5B closeout checklist",
    )
    parser.add_argument("--github-ref", default="", help="GitHub ref for the current workflow run")
    parser.add_argument("--github-sha", default="", help="GitHub SHA for the current workflow run")
    parser.add_argument("--github-event-name", default="", help="GitHub event name for the current workflow run")
    parser.add_argument("--main-branch-ref", default="refs/heads/main", help="Branch ref treated as mainline")
    parser.add_argument(
        "--mainline-ack",
        default="",
        help="Explicit acknowledgement string required when the workflow runs on the main branch",
    )
    parser.add_argument(
        "--required-mainline-ack",
        default="PROMOTE_MAIN",
        help="Expected acknowledgement string for mainline promotion runs",
    )
    parser.add_argument(
        "--enforce-main-guardrails",
        action="store_true",
        help="Exit nonzero on main when mainline readiness is not satisfied",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    promotion_target = args.promotion_target.strip() or None
    readiness = build_live_smoke_mainline_readiness(
        matrix_summary_path=args.matrix_summary,
        release_gate_path=args.release_gate,
        promotion_target=promotion_target,
        runbook_path=args.runbook_path,
        checklist_path=args.checklist_path,
        github_ref=args.github_ref,
        github_sha=args.github_sha,
        github_event_name=args.github_event_name,
        main_branch_ref=args.main_branch_ref,
        mainline_ack=args.mainline_ack,
        required_mainline_ack=args.required_mainline_ack,
    )
    bundle = build_live_smoke_release_bundle(readiness)

    readiness_json_path = out_dir / "live_smoke_mainline_readiness.json"
    readiness_markdown_path = out_dir / "live_smoke_mainline_readiness.md"
    bundle_json_path = out_dir / "live_smoke_release_bundle.json"

    readiness_json_path.write_text(json.dumps(readiness.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    readiness_markdown_path.write_text(render_live_smoke_mainline_markdown(readiness), encoding="utf-8")
    bundle_json_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(readiness_json_path)
    print(readiness_markdown_path)
    print(bundle_json_path)

    if not readiness.merge_ready:
        return 1
    if args.enforce_main_guardrails and readiness.on_main_branch and not readiness.mainline_ready:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
