from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.relationship_memory import (
    build_operator_review_queue,
    build_relationship_memory_snapshot,
    load_ingestion_records,
    render_operator_review_queue_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a relationship memory snapshot and operator review queue from ingestion records")
    parser.add_argument("--ingestion-path", required=True, help="Path to ingestion-events.jsonl or a directory containing it")
    parser.add_argument("--out-dir", required=True, help="Directory for relationship memory and review queue artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    records = load_ingestion_records(args.ingestion_path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    snapshot, suggestions = build_relationship_memory_snapshot(records)
    queue = build_operator_review_queue(records, suggestions)

    snapshot_path = out_dir / "relationship_memory.json"
    queue_path = out_dir / "operator_review_queue.json"
    queue_md_path = out_dir / "operator_review_queue.md"

    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    queue_md_path.write_text(render_operator_review_queue_markdown(queue), encoding="utf-8")

    print(snapshot_path)
    print(queue_path)
    print(queue_md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
