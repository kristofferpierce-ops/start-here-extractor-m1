from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.application_decisions import (
    apply_application_decisions,
    build_application_queue,
    load_application_decisions,
    load_target_catalog,
    render_application_queue_markdown,
    render_application_transition_rollup_markdown,
    write_jsonl,
)
from start_here_extractor.ingestion import iter_ingestion_records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply approved-to-applied transition decisions")
    parser.add_argument("--ingestion-path", required=True, help="Path to ingestion/projection JSONL records")
    parser.add_argument("--target-catalog-path", required=True, help="Path to target catalog JSON")
    parser.add_argument("--decisions-path", required=True, help="Path to application decisions JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for transition outputs")
    parser.add_argument("--actor-id", required=True, help="Actor ID applied to decisions that omit decision_by")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    records = list(iter_ingestion_records(args.ingestion_path))
    target_catalog = load_target_catalog(args.target_catalog_path)
    queue = build_application_queue(records, target_catalog)
    decisions = load_application_decisions(args.decisions_path)
    updated_records, decision_journal, rollup, post_queue = apply_application_decisions(
        records,
        queue,
        decisions,
        actor_id=args.actor_id,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "ingestion_state_applied_projection.jsonl", updated_records)
    write_jsonl(out_dir / "application_decision_journal.jsonl", decision_journal)
    (out_dir / "application_queue.json").write_text(
        json.dumps(queue, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "application_queue.md").write_text(
        render_application_queue_markdown(queue),
        encoding="utf-8",
    )
    (out_dir / "application_transition_rollup.json").write_text(
        json.dumps(rollup, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "application_transition_rollup.md").write_text(
        render_application_transition_rollup_markdown(rollup),
        encoding="utf-8",
    )
    (out_dir / "application_queue_post_apply.json").write_text(
        json.dumps(post_queue, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "application_queue_post_apply.md").write_text(
        render_application_queue_markdown(post_queue),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "record_count": len(updated_records),
                "decision_count": len(decision_journal),
                "output_dir": str(out_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
