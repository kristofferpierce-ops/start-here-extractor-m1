from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable, TextIO


def _to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    return obj


class JsonlWriter:
    def __init__(self, path: Path, *, durable: bool = False) -> None:
        self.path = path
        self.durable = durable
        self._fp: TextIO | None = None

    def __enter__(self) -> "JsonlWriter":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self.path.open("a", encoding="utf-8", newline="\n")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None

    def write_record(self, record: Any) -> None:
        if self._fp is None:
            raise RuntimeError("JsonlWriter must be used as a context manager")
        payload = _to_jsonable(record)
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self._fp.write(line)
        self._fp.write("\n")
        self._fp.flush()
        if self.durable:
            os.fsync(self._fp.fileno())

    def write_many(self, records: Iterable[Any]) -> None:
        for record in records:
            self.write_record(record)
