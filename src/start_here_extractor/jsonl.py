from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .io.jsonl_writer import JsonlWriter


def append_jsonl(path: Path, records: Iterable[Any], *, flush_each: bool = True, durable: bool = False) -> None:
    # flush_each is preserved for backward compatibility; JsonlWriter always flushes per record.
    _ = flush_each
    with JsonlWriter(path, durable=durable) as writer:
        writer.write_many(records)
