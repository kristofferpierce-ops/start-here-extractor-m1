from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, Optional


def run_advisory_scan(path: Path, command_template: Optional[str]) -> Dict[str, object]:
    if not command_template:
        return {"status": "skipped", "reason": "no-av-command-configured"}

    command = command_template.format(path=str(path))
    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return {
            "status": "completed",
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "status": "error",
            "command": command,
            "error": f"{type(exc).__name__}: {exc}",
        }
