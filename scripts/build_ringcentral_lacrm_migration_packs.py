from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.ringcentral_lacrm_migration import (
    build_ringcentral_lacrm_migration_artifacts,
    load_source_control_pipeline_documents,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build RingCentral/LACRM migration packs from source-control pipeline artifacts")
    parser.add_argument("--pipeline-dir", required=True, help="Directory containing source-control pipeline JSON artifacts")
    parser.add_argument("--out-dir", required=True, help="Directory for RingCentral/LACRM migration artifacts")
    return parser


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pipeline_docs = load_source_control_pipeline_documents(args.pipeline_dir)
    artifacts = build_ringcentral_lacrm_migration_artifacts(pipeline_docs)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "ringcentral_lacrm_migration_packs.json", artifacts["migration_packs"])
    _write_json(out_dir / "ringcentral_lacrm_migration_review_queue.json", artifacts["migration_review_queue"])
    _write_json(out_dir / "ringcentral_lacrm_migration_rollup.json", artifacts["rollup"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
