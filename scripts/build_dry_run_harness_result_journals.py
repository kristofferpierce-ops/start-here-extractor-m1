from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_harness_results import (
    build_dry_run_harness_result_journal_artifacts,
    load_replayable_dry_run_orchestration_packs,
    load_target_group_adapter_execution_harnesses,
    render_dry_run_harness_result_journals_markdown,
    render_dry_run_harness_result_review_queue_markdown,
    render_dry_run_harness_result_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build dry-run harness result journals from execution harnesses and orchestration packs")
    parser.add_argument("--target-group-adapter-execution-harnesses-path", required=True, help="Path to target_group_adapter_execution_harnesses.json")
    parser.add_argument("--replayable-dry-run-orchestration-packs-path", required=True, help="Path to replayable_dry_run_orchestration_packs.json")
    parser.add_argument("--out-dir", required=True, help="Directory for dry-run harness result artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    harnesses_doc = load_target_group_adapter_execution_harnesses(args.target_group_adapter_execution_harnesses_path)
    orchestration_doc = load_replayable_dry_run_orchestration_packs(args.replayable_dry_run_orchestration_packs_path)
    journals_doc, review_queue, rollup = build_dry_run_harness_result_journal_artifacts(harnesses_doc, orchestration_doc)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dry_run_harness_result_journals.json").write_text(json.dumps(journals_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "dry_run_harness_result_journals.md").write_text(render_dry_run_harness_result_journals_markdown(journals_doc), encoding="utf-8")
    (out_dir / "dry_run_harness_result_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "dry_run_harness_result_review_queue.md").write_text(render_dry_run_harness_result_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "dry_run_harness_result_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "dry_run_harness_result_rollup.md").write_text(render_dry_run_harness_result_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
