from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.target_group_adapter_execution_harnesses import (
    build_replayable_dry_run_orchestration_pack_artifacts,
    load_end_to_end_roundtrip_fixture_execution_packs,
    load_target_group_adapter_execution_harnesses,
    render_replayable_dry_run_orchestration_packs_markdown,
    render_replayable_dry_run_orchestration_review_queue_markdown,
    render_replayable_dry_run_orchestration_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build replayable dry-run orchestration packs from target-group execution harnesses")
    parser.add_argument("--target-group-adapter-execution-harnesses-path", required=True, help="Path to target_group_adapter_execution_harnesses.json")
    parser.add_argument("--end-to-end-roundtrip-fixture-execution-packs-path", required=True, help="Path to end_to_end_roundtrip_fixture_execution_packs.json")
    parser.add_argument("--out-dir", required=True, help="Directory for replayable dry-run orchestration artifacts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    harnesses_doc = load_target_group_adapter_execution_harnesses(args.target_group_adapter_execution_harnesses_path)
    packs_doc = load_end_to_end_roundtrip_fixture_execution_packs(args.end_to_end_roundtrip_fixture_execution_packs_path)
    orchestration_doc, review_queue, rollup = build_replayable_dry_run_orchestration_pack_artifacts(harnesses_doc, packs_doc)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "replayable_dry_run_orchestration_packs.json").write_text(json.dumps(orchestration_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "replayable_dry_run_orchestration_packs.md").write_text(render_replayable_dry_run_orchestration_packs_markdown(orchestration_doc), encoding="utf-8")
    (out_dir / "replayable_dry_run_orchestration_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "replayable_dry_run_orchestration_review_queue.md").write_text(render_replayable_dry_run_orchestration_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "replayable_dry_run_orchestration_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "replayable_dry_run_orchestration_rollup.md").write_text(render_replayable_dry_run_orchestration_rollup_markdown(rollup), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
