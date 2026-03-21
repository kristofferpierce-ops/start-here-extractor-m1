from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from start_here_extractor.ingestion import append_ingestion_record, build_ingestion_record, build_ingestion_rollup
    from start_here_extractor.utils import ensure_dir
except ModuleNotFoundError:  # pragma: no cover - direct script fallback
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    sys.modules.pop("start_here_extractor", None)
    from start_here_extractor.ingestion import append_ingestion_record, build_ingestion_record, build_ingestion_rollup
    from start_here_extractor.utils import ensure_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a generic ingestion journal from inventory JSONL artifacts")
    parser.add_argument("--inventory-dir", help="Directory containing *.inventory.jsonl files")
    parser.add_argument("--inventory-path", action="append", default=[], help="Explicit inventory JSONL file path. May be supplied more than once")
    parser.add_argument("--out-dir", required=True, help="Output directory for ingestion journal artifacts")
    parser.add_argument("--stream-name", default="ingestion-events", help="Ingestion JSONL stream name without extension")
    parser.add_argument("--source-system", default=None, help="Optional source system override stored on each ingestion record")
    parser.add_argument("--durable", action="store_true", help="fsync ingestion JSONL writes")
    return parser


def discover_inventory_paths(args: argparse.Namespace) -> list[Path]:
    paths = [Path(raw) for raw in args.inventory_path]
    if args.inventory_dir:
        paths.extend(sorted(Path(args.inventory_dir).glob("*.inventory.jsonl")))
    unique: list[Path] = []
    seen = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def load_inventory_records(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                records.append(value)
    return records


def main() -> int:
    args = build_parser().parse_args()
    inventory_paths = discover_inventory_paths(args)
    if not inventory_paths:
        raise SystemExit("no-inventory-records-found")

    out_dir = Path(args.out_dir)
    ensure_dir(out_dir)
    journal_path = out_dir / f"{args.stream_name}.jsonl"
    if journal_path.exists():
        journal_path.unlink()

    ingestion_records: list[dict] = []
    for inventory_path in inventory_paths:
        inventory_ref = f"file://{inventory_path.resolve().as_posix()}"
        for inventory_record in load_inventory_records(inventory_path):
            ingestion_record = build_ingestion_record(
                inventory_record,
                inventory_ref=inventory_ref,
                source_system=args.source_system,
            )
            append_ingestion_record(ingestion_record, out_dir, durable=bool(args.durable), stream_name=args.stream_name)
            ingestion_records.append(ingestion_record)

    rollup = build_ingestion_rollup(ingestion_records)
    rollup["journal_path"] = str(journal_path)
    rollup["inventory_paths"] = [str(path) for path in inventory_paths]
    (out_dir / "ingestion_rollup.json").write_text(json.dumps(rollup, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
