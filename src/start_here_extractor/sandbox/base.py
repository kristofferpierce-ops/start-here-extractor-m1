from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass(slots=True)
class SandboxJobRequest:
    job_id: str
    zip_path: Path
    host_staging_dir: Path
    host_results_dir: Path
    command_line: str | None = None
    timeout_seconds: int = 120
    networking_enabled: bool = False
    clipboard_enabled: bool = False
    vgpu_enabled: bool = False
    printer_redirection_enabled: bool = False
    audio_input_enabled: bool = False
    video_input_enabled: bool = False


@dataclass(slots=True)
class SandboxRunResult:
    enabled: bool
    platform: str
    dry_run: bool
    config_path: str | None = None
    command_path: str | None = None
    sentinel_path: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    exit_code: int | None = None
    timed_out: bool = False
    artifacts_dir: str | None = None
    config_summary: Dict[str, Any] | None = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SandboxRunner(ABC):
    platform: str

    @abstractmethod
    def run(self, request: SandboxJobRequest, *, dry_run: bool) -> SandboxRunResult:
        raise NotImplementedError
