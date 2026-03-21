from __future__ import annotations

import argparse
import json
from pathlib import Path

from start_here_extractor.source_control_pipeline import (
    build_source_control_pipeline_artifacts,
    iter_source_control_ingestion_records,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build source-control pipeline artifacts from ingestion records")
    parser.add_argument("--ingestion-path", required=True, help="Path to ingestion-events.jsonl or a directory containing it")
    parser.add_argument("--out-dir", required=True, help="Directory for source-control pipeline artifacts")
    return parser


def _resolve_ingestion_path(value: str) -> Path:
    path = Path(value)
    if path.is_dir():
        candidate = path / "ingestion-events.jsonl"
        if candidate.exists():
            return candidate
    return path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ingestion_path = _resolve_ingestion_path(args.ingestion_path)
    records = iter_source_control_ingestion_records(ingestion_path)
    artifacts = build_source_control_pipeline_artifacts(records)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / "source_records_raw.json", artifacts["source_records_raw"])
    _write_json(out_dir / "source_records_normalized.json", artifacts["source_records_normalized"])
    _write_json(out_dir / "candidate_matches.json", artifacts["candidate_matches"])
    _write_json(out_dir / "review_items.json", artifacts["review_items"])
    _write_json(out_dir / "approved_deltas.json", artifacts["approved_deltas"])
    _write_json(out_dir / "applied_state_transitions.json", artifacts["applied_state_transitions"])
    _write_json(out_dir / "source_control_pipeline_rollup.json", artifacts["rollup"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
