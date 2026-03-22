from __future__ import annotations

import argparse

from start_here_extractor.durable_lineage_replay import (
    build_lineage_replay_readiness_artifacts,
    load_control_documents,
    load_lineage_documents,
    load_migration_documents,
    write_json_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build lineage/replay readiness packs from durable lineage and replay-safe ingestion control artifacts")
    parser.add_argument("--lineage-dir", required=True, help="Directory containing durable lineage JSON artifacts")
    parser.add_argument("--control-dir", required=True, help="Directory containing replay-safe ingestion control JSON artifacts")
    parser.add_argument("--migration-dir", required=True, help="Directory containing RingCentral/LACRM migration JSON artifacts")
    parser.add_argument("--out-dir", required=True, help="Directory for lineage/replay readiness artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    lineage_documents = load_lineage_documents(args.lineage_dir)
    control_documents = load_control_documents(args.control_dir)
    migration_documents = load_migration_documents(args.migration_dir)
    artifacts = build_lineage_replay_readiness_artifacts(lineage_documents, control_documents, migration_documents)
    write_json_artifacts(args.out_dir, artifacts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
