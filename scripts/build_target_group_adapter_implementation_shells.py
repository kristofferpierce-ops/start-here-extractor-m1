from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_implementation_shells import (
    build_target_group_adapter_implementation_shell_artifacts,
    load_roundtrip_normalization_cases,
    load_target_group_adapter_implementation_catalog,
    load_target_group_adapter_skeletons,
    render_target_group_adapter_implementation_shell_review_queue_markdown,
    render_target_group_adapter_implementation_shell_rollup_markdown,
    render_target_group_adapter_implementation_shells_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build target-group adapter implementation shells from target-group adapter skeletons")
    parser.add_argument("--target-group-adapter-skeletons-path", required=True, help="Path to target_group_adapter_skeletons.json")
    parser.add_argument("--roundtrip-normalization-cases-path", required=True, help="Path to roundtrip_normalization_cases.json")
    parser.add_argument("--target-group-implementation-catalog-path", required=True, help="Path to target-group adapter implementation catalog JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for target-group adapter implementation shell artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    skeletons_doc = load_target_group_adapter_skeletons(args.target_group_adapter_skeletons_path)
    cases_doc = load_roundtrip_normalization_cases(args.roundtrip_normalization_cases_path)
    catalog = load_target_group_adapter_implementation_catalog(args.target_group_implementation_catalog_path)
    shells_doc, review_queue, rollup = build_target_group_adapter_implementation_shell_artifacts(skeletons_doc, cases_doc, catalog)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "target_group_adapter_implementation_shells.json").write_text(json.dumps(shells_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_implementation_shells.md").write_text(render_target_group_adapter_implementation_shells_markdown(shells_doc), encoding="utf-8")
    (out_dir / "target_group_adapter_implementation_shell_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_implementation_shell_review_queue.md").write_text(render_target_group_adapter_implementation_shell_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "target_group_adapter_implementation_shell_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_implementation_shell_rollup.md").write_text(render_target_group_adapter_implementation_shell_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
