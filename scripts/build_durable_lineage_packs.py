from __future__ import annotations

import argparse

from start_here_extractor.durable_lineage_replay import (
    build_durable_lineage_artifacts,
    load_migration_documents,
    load_source_control_pipeline_documents,
    write_json_artifacts,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build durable lineage packs from source-control pipeline and migration artifacts")
    parser.add_argument("--pipeline-dir", required=True, help="Directory containing source-control pipeline JSON artifacts")
    parser.add_argument("--migration-dir", required=True, help="Directory containing RingCentral/LACRM migration JSON artifacts")
    parser.add_argument("--out-dir", required=True, help="Directory for durable lineage artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pipeline_documents = load_source_control_pipeline_documents(args.pipeline_dir)
    migration_documents = load_migration_documents(args.migration_dir)
    artifacts = build_durable_lineage_artifacts(pipeline_documents, migration_documents)
    write_json_artifacts(args.out_dir, artifacts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
