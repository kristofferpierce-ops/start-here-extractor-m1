from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.adapter_runner_interfaces import (
    build_runner_interface_artifacts,
    load_runner_interface_catalog,
    render_runner_interface_contracts_markdown,
    render_runner_interface_review_queue_markdown,
    render_runner_interface_rollup_markdown,
)
from start_here_extractor.adapter_runners import load_runner_jobs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build runner interface contracts for adapter runner jobs")
    parser.add_argument("--runner-jobs-path", required=True, help="Path to adapter_runner_jobs.json")
    parser.add_argument("--interface-catalog-path", required=True, help="Path to runner interface catalog JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for runner interface artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    runner_jobs_doc = load_runner_jobs(args.runner_jobs_path)
    interface_catalog = load_runner_interface_catalog(args.interface_catalog_path)
    contracts_doc, review_queue, rollup = build_runner_interface_artifacts(runner_jobs_doc, interface_catalog)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "adapter_runner_interface_contracts.json").write_text(json.dumps(contracts_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "adapter_runner_interface_contracts.md").write_text(render_runner_interface_contracts_markdown(contracts_doc), encoding="utf-8")
    (out_dir / "adapter_runner_interface_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "adapter_runner_interface_review_queue.md").write_text(render_runner_interface_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "adapter_runner_interface_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "adapter_runner_interface_rollup.md").write_text(render_runner_interface_rollup_markdown(rollup), encoding="utf-8")
    print(json.dumps({"contract_count": contracts_doc.get("contract_count", 0), "review_queue_count": review_queue.get("item_count", 0), "output_dir": str(out_dir)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
