from __future__ import annotations

import argparse

from start_here_extractor.operator_console_alpha import (
    build_operator_console_alpha_artifacts,
    load_execution_documents,
    write_operator_console_alpha_artifacts,
)
from start_here_extractor.source_replay_compare import load_compare_documents, load_plan_documents
from start_here_extractor.source_replay_execution import load_approval_documents


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an enriched operator console, local draft workbench, and session package toolkit from replay plan, compare, approval, and execution artifacts"
    )
    parser.add_argument("--plan-dir", required=True, help="Directory containing source replay plan artifacts")
    parser.add_argument("--compare-dir", required=True, help="Directory containing source replay compare artifacts")
    parser.add_argument("--approval-dir", required=True, help="Directory containing source replay approval artifacts")
    parser.add_argument("--execution-dir", required=True, help="Directory containing source replay execution artifacts")
    parser.add_argument("--out-dir", required=True, help="Directory to write operator console artifacts")
    parser.add_argument(
        "--title",
        required=False,
        default="Source Replay Operator Console Alpha",
        help="Title displayed in the generated operator console",
    )
    parser.add_argument(
        "--subtitle",
        required=False,
        default="Read-only operator console and local draft workbench with session packages, history, and batch review flows for replay planning, comparison, approval, and execution triage.",
        help="Subtitle displayed in the generated operator console",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    plan_documents = load_plan_documents(args.plan_dir)
    compare_documents = load_compare_documents(args.compare_dir)
    approval_documents = load_approval_documents(args.approval_dir)
    execution_documents = load_execution_documents(args.execution_dir)
    artifacts = build_operator_console_alpha_artifacts(
        plan_documents=plan_documents,
        compare_documents=compare_documents,
        approval_documents=approval_documents,
        execution_documents=execution_documents,
        title=args.title,
        subtitle=args.subtitle,
    )
    write_operator_console_alpha_artifacts(args.out_dir, artifacts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
