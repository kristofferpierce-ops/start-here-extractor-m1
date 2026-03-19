from __future__ import annotations

from pathlib import Path
from typing import Optional

from .scan import ScanConfig, run_av_scan


def run_advisory_scan(path: Path, command_template: Optional[str], *, engine: str = "generic", timeout_seconds: int = 60):
    cfg = ScanConfig(av_engine=engine, av_command=command_template, timeout_seconds=timeout_seconds)
    return run_av_scan(path, cfg)
