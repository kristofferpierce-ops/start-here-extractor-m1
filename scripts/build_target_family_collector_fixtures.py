from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_runner_families import (
    build_target_family_collector_fixture_artifacts,
    load_target_family_runner_stubs,
    render_target_family_collector_fixtures_markdown,
    render_target_family_collector_review_queue_markdown,
    render_target_family_collector_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build normalized collector fixtures for target-family runner stubs")
    parser.add_argument("--target-runner-stubs-path", required=True, help="Path to target_family_runner_stubs.json")
    parser.add_argument("--out-dir", required=True, help="Directory for target-family collector fixture artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    stubs_doc = load_target_family_runner_stubs(args.target_runner_stubs_path)
    fixtures_doc, review_queue, rollup = build_target_family_collector_fixture_artifacts(stubs_doc)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "target_family_collector_fixtures.json").write_text(json.dumps(fixtures_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_family_collector_fixtures.md").write_text(render_target_family_collector_fixtures_markdown(fixtures_doc), encoding="utf-8")
    (out_dir / "target_family_collector_fixture_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_family_collector_fixture_review_queue.md").write_text(render_target_family_collector_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "target_family_collector_fixture_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_family_collector_fixture_rollup.md").write_text(render_target_family_collector_rollup_markdown(rollup), encoding="utf-8")
    print(json.dumps({"fixture_count": fixtures_doc.get("fixture_count", 0), "review_queue_count": review_queue.get("item_count", 0), "output_dir": str(out_dir)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
