from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.relationship_memory import (
    load_ingestion_records,
    render_operator_review_queue_markdown,
)
from start_here_extractor.review_decisions import (
    apply_review_decisions,
    load_review_decisions,
    load_review_queue,
    render_state_transition_rollup_markdown,
    write_jsonl,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply operator review decisions and build matched/approved state transition artifacts"
    )
    parser.add_argument("--ingestion-path", required=True, help="Path to ingestion-events.jsonl or its parent directory")
    parser.add_argument("--queue-path", required=True, help="Path to operator_review_queue.json or its parent directory")
    parser.add_argument("--decisions-path", required=True, help="Path to a JSON review decision file")
    parser.add_argument("--out-dir", required=True, help="Directory for updated state artifacts")
    parser.add_argument("--actor-id", default="operator-1", help="Actor identifier recorded on applied decisions")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_ingestion_records(args.ingestion_path)
    queue = load_review_queue(args.queue_path)
    decisions = load_review_decisions(args.decisions_path)
    updated_records, decision_journal, rollup, post_snapshot, post_queue = apply_review_decisions(
        records,
        queue,
        decisions,
        actor_id=args.actor_id,
    )

    projection_path = write_jsonl(out_dir / "ingestion_state_projection.jsonl", updated_records)
    journal_path = write_jsonl(out_dir / "review_decision_journal.jsonl", decision_journal)
    rollup_path = out_dir / "state_transition_rollup.json"
    rollup_md_path = out_dir / "state_transition_rollup.md"
    snapshot_path = out_dir / "relationship_memory_post_review.json"
    queue_path = out_dir / "operator_review_queue_post_review.json"
    queue_md_path = out_dir / "operator_review_queue_post_review.md"

    rollup_path.write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rollup_md_path.write_text(render_state_transition_rollup_markdown(rollup), encoding="utf-8")
    snapshot_path.write_text(json.dumps(post_snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    queue_path.write_text(json.dumps(post_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    queue_md_path.write_text(render_operator_review_queue_markdown(post_queue), encoding="utf-8")

    print(projection_path)
    print(journal_path)
    print(rollup_path)
    print(rollup_md_path)
    print(snapshot_path)
    print(queue_path)
    print(queue_md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
