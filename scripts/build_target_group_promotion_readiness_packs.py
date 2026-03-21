from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_promotion_readiness import (
    build_target_group_promotion_readiness_pack_artifacts,
    load_dry_run_harness_result_journals,
    load_replay_outcome_comparison_packs,
    render_target_group_promotion_readiness_packs_markdown,
    render_target_group_promotion_readiness_review_queue_markdown,
    render_target_group_promotion_readiness_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build target-group promotion readiness packs from dry-run result journals and replay comparison packs")
    parser.add_argument("--dry-run-harness-result-journals-path", required=True, help="Path to dry_run_harness_result_journals.json")
    parser.add_argument("--replay-outcome-comparison-packs-path", required=True, help="Path to replay_outcome_comparison_packs.json")
    parser.add_argument("--out-dir", required=True, help="Directory for promotion readiness artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    journals_doc = load_dry_run_harness_result_journals(args.dry_run_harness_result_journals_path)
    comparison_doc = load_replay_outcome_comparison_packs(args.replay_outcome_comparison_packs_path)
    packs_doc, review_queue, rollup = build_target_group_promotion_readiness_pack_artifacts(journals_doc, comparison_doc)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "target_group_promotion_readiness_packs.json").write_text(json.dumps(packs_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_promotion_readiness_packs.md").write_text(render_target_group_promotion_readiness_packs_markdown(packs_doc), encoding="utf-8")
    (out_dir / "target_group_promotion_readiness_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_promotion_readiness_review_queue.md").write_text(render_target_group_promotion_readiness_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "target_group_promotion_readiness_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_promotion_readiness_rollup.md").write_text(render_target_group_promotion_readiness_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
