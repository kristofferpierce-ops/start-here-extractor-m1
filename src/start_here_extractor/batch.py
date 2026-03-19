from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Sequence
from uuid import uuid4

from .types import BatchContext, ExtractSettings, Limits, MatchPolicy


@dataclass(frozen=True)
class BatchConfig:
    targets: Sequence[Path]
    fail_fast: bool = False
    sort_paths: bool = True
    job_id: str | None = None
    max_attempts: int = 1


def iter_targets(config: BatchConfig) -> list[Path]:
    unique = {target.resolve() if target.exists() else target for target in config.targets}
    ordered = sorted(unique, key=lambda path: str(path).lower()) if config.sort_paths else list(unique)
    return ordered


def run_batch(
    config: BatchConfig,
    *,
    limits: Limits,
    policy: MatchPolicy,
    settings: ExtractSettings,
    output_root: Path,
    process_one: Callable[..., object],
) -> Iterator[object]:
    job_id = config.job_id or str(uuid4())
    accepts_batch_context = "batch_context" in inspect.signature(process_one).parameters

    for zip_path in iter_targets(config):
        per_zip_output_dir = output_root / _slug(zip_path.stem)
        per_zip_output_dir.mkdir(parents=True, exist_ok=True)
        batch_context = BatchContext(job_id=job_id, attempt=1, max_attempts=config.max_attempts)
        if accepts_batch_context:
            result = process_one(zip_path, per_zip_output_dir, limits, policy, settings, batch_context=batch_context)
        else:
            result = process_one(zip_path, per_zip_output_dir, limits, policy, settings)
        yield result
        if config.fail_fast and getattr(result, "errors", None):
            break


def _slug(value: str) -> str:
    import re

    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "artifact"
