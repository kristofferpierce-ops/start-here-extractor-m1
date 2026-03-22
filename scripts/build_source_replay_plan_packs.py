from __future__ import annotations

import argparse

from start_here_extractor.source_replay_plans import (
    build_source_replay_plan_artifacts,
    load_control_documents,
    load_lineage_documents,
    load_migration_documents,
    load_readiness_documents,
    load_source_control_pipeline_documents,
    write_json_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build source replay plan packs from source-control, lineage, control, and readiness artifacts")
    parser.add_argument("--pipeline-dir", required=True, help="Directory containing source-control pipeline JSON artifacts")
    parser.add_argument("--migration-dir", required=True, help="Directory containing RingCentral/LACRM migration JSON artifacts")
    parser.add_argument("--lineage-dir", required=True, help="Directory containing durable lineage JSON artifacts")
    parser.add_argument("--control-dir", required=True, help="Directory containing replay-safe ingestion control JSON artifacts")
    parser.add_argument("--readiness-dir", required=True, help="Directory containing lineage/replay readiness JSON artifacts")
    parser.add_argument("--out-dir", required=True, help="Directory for source replay plan artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pipeline_documents = load_source_control_pipeline_documents(args.pipeline_dir)
    migration_documents = load_migration_documents(args.migration_dir)
    lineage_documents = load_lineage_documents(args.lineage_dir)
    control_documents = load_control_documents(args.control_dir)
    readiness_documents = load_readiness_documents(args.readiness_dir)
    artifacts = build_source_replay_plan_artifacts(
        pipeline_documents,
        migration_documents,
        lineage_documents,
        control_documents,
        readiness_documents,
    )
    write_json_artifacts(args.out_dir, artifacts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
