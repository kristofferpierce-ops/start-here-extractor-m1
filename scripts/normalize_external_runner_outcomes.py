from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.adapter_runner_interfaces import (
    load_raw_external_runner_payloads,
    load_runner_interface_contracts,
    normalize_external_runner_outcomes,
    render_collector_normalization_review_queue_markdown,
    render_collector_normalization_rollup_markdown,
    render_normalized_external_outcomes_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize raw external runner payloads into canonical collector outcomes")
    parser.add_argument("--interface-contracts-path", required=True, help="Path to adapter_runner_interface_contracts.json")
    parser.add_argument("--payloads-path", required=True, help="Path to raw external runner payloads JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for normalized collector artifacts")
    parser.add_argument("--actor-id", required=True, help="Actor ID applied when payloads omit executed_by")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    interface_contracts_doc = load_runner_interface_contracts(args.interface_contracts_path)
    payloads = load_raw_external_runner_payloads(args.payloads_path)
    outcomes_doc, review_queue, rollup = normalize_external_runner_outcomes(interface_contracts_doc, payloads, actor_id=args.actor_id)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "normalized_external_runner_outcomes.json").write_text(json.dumps(outcomes_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "normalized_external_runner_outcomes.md").write_text(render_normalized_external_outcomes_markdown(outcomes_doc), encoding="utf-8")
    (out_dir / "collector_normalization_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "collector_normalization_review_queue.md").write_text(render_collector_normalization_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "collector_normalization_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "collector_normalization_rollup.md").write_text(render_collector_normalization_rollup_markdown(rollup), encoding="utf-8")
    print(json.dumps({"outcome_count": outcomes_doc.get("outcome_count", 0), "review_queue_count": review_queue.get("item_count", 0), "output_dir": str(out_dir)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
