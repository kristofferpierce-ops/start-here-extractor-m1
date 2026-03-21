from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_skeletons import (
    build_target_group_adapter_skeleton_artifacts,
    load_canonical_request_response_fixture_packs,
    load_target_group_adapter_packages,
    load_target_group_adapter_skeleton_catalog,
    render_target_group_adapter_skeleton_review_queue_markdown,
    render_target_group_adapter_skeleton_rollup_markdown,
    render_target_group_adapter_skeletons_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build concrete target-group adapter skeletons from target-group adapter packages")
    parser.add_argument("--target-group-packages-path", required=True, help="Path to target_group_adapter_packages.json")
    parser.add_argument("--request-response-fixture-packs-path", required=True, help="Path to canonical_request_response_fixture_packs.json")
    parser.add_argument("--target-group-skeleton-catalog-path", required=True, help="Path to target-group adapter skeleton catalog JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for target-group adapter skeleton artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    packages_doc = load_target_group_adapter_packages(args.target_group_packages_path)
    fixture_packs_doc = load_canonical_request_response_fixture_packs(args.request_response_fixture_packs_path)
    catalog = load_target_group_adapter_skeleton_catalog(args.target_group_skeleton_catalog_path)
    skeletons_doc, review_queue, rollup = build_target_group_adapter_skeleton_artifacts(packages_doc, fixture_packs_doc, catalog)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "target_group_adapter_skeletons.json").write_text(json.dumps(skeletons_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_skeletons.md").write_text(render_target_group_adapter_skeletons_markdown(skeletons_doc), encoding="utf-8")
    (out_dir / "target_group_adapter_skeleton_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_skeleton_review_queue.md").write_text(render_target_group_adapter_skeleton_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "target_group_adapter_skeleton_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_skeleton_rollup.md").write_text(render_target_group_adapter_skeleton_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
