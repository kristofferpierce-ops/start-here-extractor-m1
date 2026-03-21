from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.adapter_execution import (
    apply_adapter_execution_outcomes,
    load_adapter_execution_contracts,
    load_execution_decisions,
    render_adapter_execution_contracts_post_execute_markdown,
    render_adapter_execution_journal_markdown,
    render_adapter_execution_rollup_markdown,
)
from start_here_extractor.ingestion import iter_ingestion_records
from start_here_extractor.io.jsonl_writer import JsonlWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply adapter execution outcomes and ingest the results into projected records")
    parser.add_argument("--ingestion-path", required=True, help="Path to applied ingestion/projection JSONL records")
    parser.add_argument("--contracts-path", required=True, help="Path to adapter_execution_contracts.json")
    parser.add_argument("--decisions-path", required=True, help="Path to adapter execution decisions JSON")
    parser.add_argument("--out-dir", required=True, help="Directory for execution outcome outputs")
    parser.add_argument("--actor-id", required=True, help="Actor ID applied to decisions that omit executed_by/decision_by")
    return parser


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with JsonlWriter(path, durable=False) as writer:
        for row in rows:
            writer.write_record(row)


def main() -> int:
    args = build_parser().parse_args()
    records = list(iter_ingestion_records(args.ingestion_path))
    contracts_doc = load_adapter_execution_contracts(args.contracts_path)
    decisions = load_execution_decisions(args.decisions_path)
    updated_records, updated_contracts_doc, journal, rollup = apply_adapter_execution_outcomes(
        records,
        contracts_doc,
        decisions,
        actor_id=args.actor_id,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out_dir / "ingestion_state_execution_projection.jsonl", updated_records)
    _write_jsonl(out_dir / "adapter_execution_journal.jsonl", journal)
    (out_dir / "adapter_execution_contracts_post_execute.json").write_text(
        json.dumps(updated_contracts_doc, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "adapter_execution_contracts_post_execute.md").write_text(
        render_adapter_execution_contracts_post_execute_markdown(updated_contracts_doc),
        encoding="utf-8",
    )
    (out_dir / "adapter_execution_rollup.json").write_text(
        json.dumps(rollup, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "adapter_execution_rollup.md").write_text(
        render_adapter_execution_rollup_markdown(rollup),
        encoding="utf-8",
    )
    (out_dir / "adapter_execution_journal.md").write_text(
        render_adapter_execution_journal_markdown(journal),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "record_count": len(updated_records),
                "contract_count": updated_contracts_doc.get("contract_count", 0),
                "journal_count": len(journal),
                "output_dir": str(out_dir),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
