from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.family_interface_templates import (
    build_canonical_raw_payload_contract_artifacts,
    load_family_interface_templates,
    render_canonical_raw_payload_contracts_markdown,
    render_canonical_raw_payload_review_queue_markdown,
    render_canonical_raw_payload_rollup_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build canonical raw payload contracts from family interface templates")
    parser.add_argument("--family-interface-templates-path", required=True, help="Path to family_interface_templates.json")
    parser.add_argument("--out-dir", required=True, help="Directory for canonical raw payload contract artifacts")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    templates_doc = load_family_interface_templates(args.family_interface_templates_path)
    contracts_doc, review_queue, rollup = build_canonical_raw_payload_contract_artifacts(templates_doc)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "canonical_raw_payload_contracts.json").write_text(json.dumps(contracts_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "canonical_raw_payload_contracts.md").write_text(render_canonical_raw_payload_contracts_markdown(contracts_doc), encoding="utf-8")
    (out_dir / "canonical_raw_payload_review_queue.json").write_text(json.dumps(review_queue, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "canonical_raw_payload_review_queue.md").write_text(render_canonical_raw_payload_review_queue_markdown(review_queue), encoding="utf-8")
    (out_dir / "canonical_raw_payload_rollup.json").write_text(json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "canonical_raw_payload_rollup.md").write_text(render_canonical_raw_payload_rollup_markdown(rollup), encoding="utf-8")
    print(json.dumps({"contract_count": contracts_doc.get("contract_count", 0), "review_queue_count": review_queue.get("item_count", 0), "output_dir": str(out_dir)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
