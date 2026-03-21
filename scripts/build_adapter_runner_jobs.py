from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.adapter_execution import load_adapter_execution_contracts
from start_here_extractor.adapter_runners import (
    build_adapter_runner_job_artifacts,
    load_runner_catalog,
    render_adapter_runner_jobs_markdown,
    render_adapter_runner_review_queue_markdown,
    render_adapter_runner_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build adapter runner job stubs for execution contracts")
    parser.add_argument("--contracts-path", required=True, help="Path to adapter_execution_contracts.json or post-execute contracts JSON")
    parser.add_argument("--runner-catalog-path", required=True, help="Path to runner catalog JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for adapter runner job artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    contracts_doc = load_adapter_execution_contracts(args.contracts_path)
    runner_catalog = load_runner_catalog(args.runner_catalog_path)
    jobs_doc, review_queue, rollup = build_adapter_runner_job_artifacts(contracts_doc, runner_catalog)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "adapter_runner_jobs.json").write_text(json.dumps(jobs_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "adapter_runner_jobs.md").write_text(render_adapter_runner_jobs_markdown(jobs_doc), encoding="utf-8")
    (out_dir / "adapter_runner_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "adapter_runner_review_queue.md").write_text(render_adapter_runner_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "adapter_runner_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "adapter_runner_rollup.md").write_text(render_adapter_runner_rollup_markdown(rollup), encoding="utf-8")
    print(json.dumps({"job_count": jobs_doc.get("job_count", 0), "review_queue_count": review_queue.get("item_count", 0), "output_dir": str(out_dir)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
