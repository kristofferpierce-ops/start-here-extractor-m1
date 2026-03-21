from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_promotion_readiness import (
    build_live_integration_candidate_pack_artifacts,
    load_target_group_promotion_readiness_packs,
    render_live_integration_candidate_packs_markdown,
    render_live_integration_candidate_review_queue_markdown,
    render_live_integration_candidate_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build live integration candidate packs from promotion readiness packs")
    parser.add_argument("--target-group-promotion-readiness-packs-path", required=True, help="Path to target_group_promotion_readiness_packs.json")
    parser.add_argument("--out-dir", required=True, help="Directory for live integration candidate artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    readiness_doc = load_target_group_promotion_readiness_packs(args.target_group_promotion_readiness_packs_path)
    packs_doc, review_queue, rollup = build_live_integration_candidate_pack_artifacts(readiness_doc)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "live_integration_candidate_packs.json").write_text(json.dumps(packs_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "live_integration_candidate_packs.md").write_text(render_live_integration_candidate_packs_markdown(packs_doc), encoding="utf-8")
    (out_dir / "live_integration_candidate_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "live_integration_candidate_review_queue.md").write_text(render_live_integration_candidate_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "live_integration_candidate_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "live_integration_candidate_rollup.md").write_text(render_live_integration_candidate_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
