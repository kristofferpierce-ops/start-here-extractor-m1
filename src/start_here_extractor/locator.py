from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator, List

from .utils import dedupe_paths


def iter_zip_paths(explicit_paths: Iterable[str], roots: Iterable[str], allow_symlink_traversal: bool = False) -> Iterator[Path]:
    for raw in explicit_paths:
        path = Path(raw)
        if path.is_file() and path.suffix.lower() == ".zip":
            yield path

    for raw in roots:
        root = Path(raw)
        if not root.exists():
            continue
        for path in root.rglob("*.zip"):
            if path.is_symlink() and not allow_symlink_traversal:
                continue
            if path.is_file():
                yield path


def discover_zip_paths(explicit_paths: Iterable[str], roots: Iterable[str], allow_symlink_traversal: bool = False) -> List[Path]:
    return dedupe_paths(iter_zip_paths(explicit_paths, roots, allow_symlink_traversal=allow_symlink_traversal))
