from __future__ import annotations

import argparse

from start_here_extractor.source_replay_approval import (
    build_source_replay_approval_artifacts,
    write_source_replay_approval_artifacts,
)
from start_here_extractor.source_replay_compare import (
    load_compare_documents,
    load_plan_documents,
)
from start_here_extractor.source_replay_plans import (
    load_control_documents,
    load_lineage_documents,
    load_migration_documents,
    load_readiness_documents,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build source replay approval journals from replay comparison, replay plans, "
            "readiness, replay-safe controls, durable lineage, and migration artifacts"
        )
    )
    parser.add_argument(
        "--pipeline-dir",
        required=False,
        help=(
            "Directory containing source-control pipeline JSON artifacts. "
            "Accepted for interface consistency with the milestone test flow."
        ),
    )
    parser.add_argument(
        "--compare-dir",
        required=True,
        help="Directory containing source replay comparison JSON artifacts",
    )
    parser.add_argument(
        "--plan-dir",
        required=True,
        help="Directory containing source replay plan JSON artifacts",
    )
    parser.add_argument(
        "--readiness-dir",
        required=True,
        help="Directory containing lineage and replay readiness JSON artifacts",
    )
    parser.add_argument(
        "--control-dir",
        required=True,
        help="Directory containing replay-safe ingestion control JSON artifacts",
    )
    parser.add_argument(
        "--lineage-dir",
        required=True,
        help="Directory containing durable lineage JSON artifacts",
    )
    parser.add_argument(
        "--migration-dir",
        required=True,
        help="Directory containing migration JSON artifacts",
    )
    parser.add_argument("--out-dir", required=True, help="Directory to write approval artifacts")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    compare_documents = load_compare_documents(args.compare_dir)
    plan_documents = load_plan_documents(args.plan_dir)
    readiness_documents = load_readiness_documents(args.readiness_dir)
    control_documents = load_control_documents(args.control_dir)
    lineage_documents = load_lineage_documents(args.lineage_dir)
    migration_documents = load_migration_documents(args.migration_dir)
    artifacts = build_source_replay_approval_artifacts(
        compare_documents=compare_documents,
        plan_documents=plan_documents,
        readiness_documents=readiness_documents,
        control_documents=control_documents,
        lineage_documents=lineage_documents,
        migration_documents=migration_documents,
    )
    write_source_replay_approval_artifacts(args.out_dir, artifacts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
