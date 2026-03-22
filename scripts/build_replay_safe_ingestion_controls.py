from __future__ import annotations

import argparse

from start_here_extractor.durable_lineage_replay import (
    build_replay_safe_ingestion_control_artifacts,
    load_lineage_documents,
    load_migration_documents,
    write_json_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build replay-safe ingestion controls from durable lineage artifacts")
    parser.add_argument("--lineage-dir", required=True, help="Directory containing durable lineage JSON artifacts")
    parser.add_argument("--migration-dir", required=True, help="Directory containing RingCentral/LACRM migration JSON artifacts")
    parser.add_argument("--out-dir", required=True, help="Directory for replay-safe ingestion control artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    lineage_documents = load_lineage_documents(args.lineage_dir)
    migration_documents = load_migration_documents(args.migration_dir)
    artifacts = build_replay_safe_ingestion_control_artifacts(lineage_documents, migration_documents)
    write_json_artifacts(args.out_dir, artifacts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
