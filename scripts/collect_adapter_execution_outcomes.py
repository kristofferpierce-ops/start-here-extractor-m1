from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.adapter_runners import (
    collect_adapter_execution_outcomes,
    load_external_outcome_payloads,
    load_runner_jobs,
    render_external_outcome_decisions_markdown,
    render_external_outcome_review_queue_markdown,
    render_external_outcome_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect external execution outcomes and normalize them into adapter execution decisions")
    parser.add_argument("--runner-jobs-path", required=True, help="Path to adapter_runner_jobs.json")
    parser.add_argument("--payloads-path", required=True, help="Path to external runner outcomes JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for collected execution outcome artifacts")
    parser.add_argument("--actor-id", required=True, help="Actor ID applied to outcomes that omit executed_by")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    runner_jobs_doc = load_runner_jobs(args.runner_jobs_path)
    payloads = load_external_outcome_payloads(args.payloads_path)
    decisions_doc, review_queue, rollup = collect_adapter_execution_outcomes(runner_jobs_doc, payloads, actor_id=args.actor_id)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "collected_adapter_execution_decisions.json").write_text(json.dumps(decisions_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "collected_adapter_execution_decisions.md").write_text(render_external_outcome_decisions_markdown(decisions_doc), encoding="utf-8")
    (out_dir / "external_outcome_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "external_outcome_review_queue.md").write_text(render_external_outcome_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "external_outcome_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "external_outcome_rollup.md").write_text(render_external_outcome_rollup_markdown(rollup), encoding="utf-8")
    print(json.dumps({"decision_count": decisions_doc.get("decision_count", 0), "review_queue_count": review_queue.get("item_count", 0), "output_dir": str(out_dir)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
