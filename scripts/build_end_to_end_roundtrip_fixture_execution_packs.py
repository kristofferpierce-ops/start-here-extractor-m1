from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_implementation_shells import (
    build_end_to_end_roundtrip_fixture_execution_pack_artifacts,
    load_roundtrip_normalization_cases,
    load_target_group_adapter_implementation_shells,
    render_end_to_end_roundtrip_fixture_execution_packs_markdown,
    render_end_to_end_roundtrip_fixture_execution_review_queue_markdown,
    render_end_to_end_roundtrip_fixture_execution_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build end-to-end round-trip fixture execution packs from target-group adapter implementation shells")
    parser.add_argument("--target-group-adapter-implementation-shells-path", required=True, help="Path to target_group_adapter_implementation_shells.json")
    parser.add_argument("--roundtrip-normalization-cases-path", required=True, help="Path to roundtrip_normalization_cases.json")
    parser.add_argument("--out-dir", required=True, help="Directory for end-to-end round-trip fixture execution pack artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    shells_doc = load_target_group_adapter_implementation_shells(args.target_group_adapter_implementation_shells_path)
    cases_doc = load_roundtrip_normalization_cases(args.roundtrip_normalization_cases_path)
    packs_doc, review_queue, rollup = build_end_to_end_roundtrip_fixture_execution_pack_artifacts(shells_doc, cases_doc)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "end_to_end_roundtrip_fixture_execution_packs.json").write_text(json.dumps(packs_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "end_to_end_roundtrip_fixture_execution_packs.md").write_text(render_end_to_end_roundtrip_fixture_execution_packs_markdown(packs_doc), encoding="utf-8")
    (out_dir / "end_to_end_roundtrip_fixture_execution_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "end_to_end_roundtrip_fixture_execution_review_queue.md").write_text(render_end_to_end_roundtrip_fixture_execution_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "end_to_end_roundtrip_fixture_execution_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "end_to_end_roundtrip_fixture_execution_rollup.md").write_text(render_end_to_end_roundtrip_fixture_execution_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
