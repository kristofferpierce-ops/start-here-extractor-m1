from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_execution_harnesses import (
    build_target_group_adapter_execution_harness_artifacts,
    load_end_to_end_roundtrip_fixture_execution_packs,
    load_target_group_adapter_implementation_shells,
    load_target_group_execution_harness_catalog,
    render_target_group_adapter_execution_harness_review_queue_markdown,
    render_target_group_adapter_execution_harness_rollup_markdown,
    render_target_group_adapter_execution_harnesses_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build target-group adapter execution harnesses from implementation shells")
    parser.add_argument("--target-group-adapter-implementation-shells-path", required=True, help="Path to target_group_adapter_implementation_shells.json")
    parser.add_argument("--end-to-end-roundtrip-fixture-execution-packs-path", required=True, help="Path to end_to_end_roundtrip_fixture_execution_packs.json")
    parser.add_argument("--target-group-execution-harness-catalog-path", required=True, help="Path to target-group execution harness catalog JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for target-group adapter execution harness artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    shells_doc = load_target_group_adapter_implementation_shells(args.target_group_adapter_implementation_shells_path)
    packs_doc = load_end_to_end_roundtrip_fixture_execution_packs(args.end_to_end_roundtrip_fixture_execution_packs_path)
    catalog = load_target_group_execution_harness_catalog(args.target_group_execution_harness_catalog_path)
    harnesses_doc, review_queue, rollup = build_target_group_adapter_execution_harness_artifacts(shells_doc, packs_doc, catalog)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "target_group_adapter_execution_harnesses.json").write_text(json.dumps(harnesses_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_execution_harnesses.md").write_text(render_target_group_adapter_execution_harnesses_markdown(harnesses_doc), encoding="utf-8")
    (out_dir / "target_group_adapter_execution_harness_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_execution_harness_review_queue.md").write_text(render_target_group_adapter_execution_harness_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "target_group_adapter_execution_harness_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_group_adapter_execution_harness_rollup.md").write_text(render_target_group_adapter_execution_harness_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
