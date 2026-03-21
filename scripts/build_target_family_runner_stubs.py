from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.adapter_runner_interfaces import load_runner_interface_contracts
from start_here_extractor.target_runner_families import (
    build_target_family_runner_stub_artifacts,
    load_target_family_catalog,
    render_target_family_runner_review_queue_markdown,
    render_target_family_runner_rollup_markdown,
    render_target_family_runner_stubs_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build concrete target-family runner stubs from runner interface contracts")
    parser.add_argument("--interface-contracts-path", required=True, help="Path to adapter_runner_interface_contracts.json")
    parser.add_argument("--target-family-catalog-path", required=True, help="Path to target family catalog JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for target-family runner stub artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    contracts_doc = load_runner_interface_contracts(args.interface_contracts_path)
    target_family_catalog = load_target_family_catalog(args.target_family_catalog_path)
    stubs_doc, review_queue, rollup = build_target_family_runner_stub_artifacts(contracts_doc, target_family_catalog)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "target_family_runner_stubs.json").write_text(json.dumps(stubs_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_family_runner_stubs.md").write_text(render_target_family_runner_stubs_markdown(stubs_doc), encoding="utf-8")
    (out_dir / "target_family_runner_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_family_runner_review_queue.md").write_text(render_target_family_runner_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "target_family_runner_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "target_family_runner_rollup.md").write_text(render_target_family_runner_rollup_markdown(rollup), encoding="utf-8")
    print(json.dumps({"stub_count": stubs_doc.get("stub_count", 0), "review_queue_count": review_queue.get("item_count", 0), "output_dir": str(out_dir)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
