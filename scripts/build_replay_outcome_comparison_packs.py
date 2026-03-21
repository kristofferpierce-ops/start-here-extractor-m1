from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_harness_results import (
    build_replay_outcome_comparison_pack_artifacts,
    load_dry_run_harness_result_journals,
    load_replayable_dry_run_orchestration_packs,
    render_replay_outcome_comparison_packs_markdown,
    render_replay_outcome_comparison_review_queue_markdown,
    render_replay_outcome_comparison_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build replay outcome comparison packs from dry-run harness results and orchestration packs")
    parser.add_argument("--dry-run-harness-result-journals-path", required=True, help="Path to dry_run_harness_result_journals.json")
    parser.add_argument("--replayable-dry-run-orchestration-packs-path", required=True, help="Path to replayable_dry_run_orchestration_packs.json")
    parser.add_argument("--out-dir", required=True, help="Directory for replay outcome comparison artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    journals_doc = load_dry_run_harness_result_journals(args.dry_run_harness_result_journals_path)
    orchestration_doc = load_replayable_dry_run_orchestration_packs(args.replayable_dry_run_orchestration_packs_path)
    comparison_doc, review_queue, rollup = build_replay_outcome_comparison_pack_artifacts(journals_doc, orchestration_doc)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "replay_outcome_comparison_packs.json").write_text(json.dumps(comparison_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "replay_outcome_comparison_packs.md").write_text(render_replay_outcome_comparison_packs_markdown(comparison_doc), encoding="utf-8")
    (out_dir / "replay_outcome_comparison_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "replay_outcome_comparison_review_queue.md").write_text(render_replay_outcome_comparison_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "replay_outcome_comparison_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "replay_outcome_comparison_rollup.md").write_text(render_replay_outcome_comparison_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
