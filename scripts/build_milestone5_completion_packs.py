from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_milestone_closeout import (
    build_milestone5_completion_pack_artifacts,
    load_m5c_closeout_packs,
    load_m5c_closeout_review_queue,
    render_milestone5_completion_packs_markdown,
    render_milestone5_completion_review_queue_markdown,
    render_milestone5_completion_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Milestone 5 completion packs from M5C closeout artifacts")
    parser.add_argument("--m5c-closeout-packs-path", required=True, help="Path to m5c_closeout_packs.json")
    parser.add_argument("--m5c-closeout-review-queue-path", required=True, help="Path to m5c_closeout_review_queue.json")
    parser.add_argument("--out-dir", required=True, help="Directory for Milestone 5 completion artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    closeout_doc = load_m5c_closeout_packs(args.m5c_closeout_packs_path)
    closeout_review_queue = load_m5c_closeout_review_queue(args.m5c_closeout_review_queue_path)
    packs_doc, review_queue, rollup = build_milestone5_completion_pack_artifacts(closeout_doc, closeout_review_queue)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "milestone5_completion_packs.json").write_text(json.dumps(packs_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "milestone5_completion_packs.md").write_text(render_milestone5_completion_packs_markdown(packs_doc), encoding="utf-8")
    (out_dir / "milestone5_completion_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "milestone5_completion_review_queue.md").write_text(render_milestone5_completion_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "milestone5_completion_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "milestone5_completion_rollup.md").write_text(render_milestone5_completion_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
