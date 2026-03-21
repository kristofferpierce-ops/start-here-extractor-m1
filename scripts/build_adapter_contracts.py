from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.adapter_contracts import (
    build_adapter_execution_artifacts,
    load_adapter_catalog,
    render_adapter_contract_review_queue_markdown,
    render_adapter_contract_rollup_markdown,
    render_adapter_execution_contracts_markdown,
)
from start_here_extractor.ingestion import iter_ingestion_records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build adapter execution contract scaffolding for applied records")
    parser.add_argument("--ingestion-path", required=True, help="Path to applied ingestion/projection JSONL records")
    parser.add_argument("--adapter-catalog-path", required=True, help="Path to adapter catalog JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for adapter contract outputs")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    records = list(iter_ingestion_records(args.ingestion_path))
    adapter_catalog = load_adapter_catalog(args.adapter_catalog_path)
    contracts_doc, review_queue, rollup = build_adapter_execution_artifacts(records, adapter_catalog)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "adapter_execution_contracts.json").write_text(
        json.dumps(contracts_doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "adapter_execution_contracts.md").write_text(
        render_adapter_execution_contracts_markdown(contracts_doc),
        encoding="utf-8",
    )
    (out_dir / "adapter_contract_review_queue.json").write_text(
        json.dumps(review_queue, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "adapter_contract_review_queue.md").write_text(
        render_adapter_contract_review_queue_markdown(review_queue),
        encoding="utf-8",
    )
    (out_dir / "adapter_contract_rollup.json").write_text(
        json.dumps(rollup, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "adapter_contract_rollup.md").write_text(
        render_adapter_contract_rollup_markdown(rollup),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "record_count": len(records),
                "contract_count": contracts_doc.get("contract_count", 0),
                "review_queue_count": review_queue.get("item_count", 0),
                "output_dir": str(out_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
