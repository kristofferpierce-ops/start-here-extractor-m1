from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Tuple

WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def hash_file(path: Path, algorithm: str, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    return hash_file(path, "sha256", chunk_size=chunk_size)


def md5_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    return hash_file(path, "md5", chunk_size=chunk_size)


def normalize_name(value: str) -> str:
    base = Path(value).stem.lower()
    return re.sub(r"[^a-z0-9]", "", base)


def normalize_ext(value: str) -> str:
    return Path(value).suffix.lower()


def suspicious_zip_member(name: str) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if "\x00" in name:
        reasons.append("nul-byte")
    if name.startswith("/") or name.startswith("\\"):
        reasons.append("absolute-root")
    if WINDOWS_DRIVE_RE.match(name):
        reasons.append("windows-drive")
    if name.startswith("//") or name.startswith("\\\\"):
        reasons.append("unc-path")
    normalized = name.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if any(part == ".." for part in parts):
        reasons.append("parent-traversal")
    return bool(reasons), reasons


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def dedupe_paths(paths: Iterable[Path]) -> List[Path]:
    seen = set()
    output: List[Path] = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        output.append(path)
    return output


def safe_slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "artifact"
