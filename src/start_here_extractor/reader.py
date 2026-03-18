from __future__ import annotations

from pathlib import Path

from .types import PreviewResult


ENCODING_ORDER = ["utf-8", "utf-16", "utf-16-le", "utf-16-be"]


def read_preview(path: Path, preview_bytes: int, preview_lines: int) -> PreviewResult:
    payload = path.read_bytes()[:preview_bytes]
    for encoding in ENCODING_ORDER:
        try:
            text = payload.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        encoding = "utf-8-replace"
        text = payload.decode("utf-8", errors="replace")

    lines = text.splitlines()
    bounded = "\n".join(lines[:preview_lines])
    return PreviewResult(
        encoding=encoding,
        text=bounded,
        bytes_read=len(payload),
        lines=min(len(lines), preview_lines),
    )
