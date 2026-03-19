from __future__ import annotations

import shutil
import subprocess
import textwrap
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .base import SandboxJobRequest, SandboxRunResult, SandboxRunner
from ..utils import ensure_dir

SANDBOX_PLATFORM = "windows-sandbox"
DEFAULT_WINDOWS_SANDBOX_EXE = r"C:\Windows\System32\WindowsSandbox.exe"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WindowsSandboxRunner(SandboxRunner):
    platform = SANDBOX_PLATFORM

    def __init__(self, sandbox_exe: str | Path | None = None) -> None:
        self.sandbox_exe = Path(sandbox_exe) if sandbox_exe else Path(DEFAULT_WINDOWS_SANDBOX_EXE)

    @staticmethod
    def _bool_setting(enabled: bool) -> str:
        return "Enable" if enabled else "Disable"

    def build_sandbox_folders(self, request: SandboxJobRequest) -> tuple[str, str]:
        staging_folder = r"C:\Sandbox\Staging"
        results_folder = r"C:\Sandbox\Results"
        return staging_folder, results_folder

    def render_wsb_xml(self, request: SandboxJobRequest) -> str:
        sandbox_staging, sandbox_results = self.build_sandbox_folders(request)
        logon_command = fr"powershell.exe -ExecutionPolicy Bypass -File {sandbox_staging}\run_job.ps1"

        root = ET.Element("Configuration")
        ET.SubElement(root, "Networking").text = self._bool_setting(request.networking_enabled)
        ET.SubElement(root, "vGPU").text = self._bool_setting(request.vgpu_enabled)
        ET.SubElement(root, "ClipboardRedirection").text = self._bool_setting(request.clipboard_enabled)
        ET.SubElement(root, "PrinterRedirection").text = self._bool_setting(request.printer_redirection_enabled)
        ET.SubElement(root, "AudioInput").text = self._bool_setting(request.audio_input_enabled)
        ET.SubElement(root, "VideoInput").text = self._bool_setting(request.video_input_enabled)

        mapped_folders = ET.SubElement(root, "MappedFolders")
        staging_folder = ET.SubElement(mapped_folders, "MappedFolder")
        ET.SubElement(staging_folder, "HostFolder").text = str(request.host_staging_dir.resolve())
        ET.SubElement(staging_folder, "SandboxFolder").text = sandbox_staging
        ET.SubElement(staging_folder, "ReadOnly").text = "true"

        results_folder = ET.SubElement(mapped_folders, "MappedFolder")
        ET.SubElement(results_folder, "HostFolder").text = str(request.host_results_dir.resolve())
        ET.SubElement(results_folder, "SandboxFolder").text = sandbox_results
        ET.SubElement(results_folder, "ReadOnly").text = "false"

        logon = ET.SubElement(root, "LogonCommand")
        ET.SubElement(logon, "Command").text = logon_command

        xml = ET.tostring(root, encoding="unicode")
        return '<?xml version="1.0" encoding="utf-8"?>\n' + xml + "\n"

    def _default_command_for_script(self, request: SandboxJobRequest) -> str:
        return request.command_line or 'Write-Host "No sandbox command configured; writing sentinel only."'

    def render_job_script(self, request: SandboxJobRequest) -> str:
        sandbox_staging, sandbox_results = self.build_sandbox_folders(request)
        sentinel_path = fr"{sandbox_results}\job.completed.json"
        command = self._default_command_for_script(request)
        script = textwrap.dedent(
            f"""
            $ErrorActionPreference = 'Stop'
            $sentinel = '{sentinel_path}'
            $started = [DateTimeOffset]::UtcNow.ToString('o')
            $exitCode = 0
            $status = 'completed'
            try {{
                {command}
            }} catch {{
                $status = 'failed'
                $exitCode = 1
            }} finally {{
                $ended = [DateTimeOffset]::UtcNow.ToString('o')
                $payload = @{{
                    status = $status
                    exit_code = $exitCode
                    started_at = $started
                    ended_at = $ended
                    zip_path = '{Path(request.zip_path).name}'
                }} | ConvertTo-Json -Compress
                Set-Content -Path $sentinel -Value $payload -Encoding UTF8
                if ($exitCode -ne 0) {{ exit $exitCode }}
            }}
            """
        ).strip() + "\n"
        return script

    def stage_job(self, request: SandboxJobRequest) -> tuple[Path, Path, Path]:
        ensure_dir(request.host_staging_dir)
        ensure_dir(request.host_results_dir)
        staged_zip = request.host_staging_dir / Path(request.zip_path).name
        if request.zip_path.exists():
            shutil.copy2(request.zip_path, staged_zip)

        command_path = request.host_staging_dir / "run_job.ps1"
        command_path.write_text(self.render_job_script(request), encoding="utf-8", newline="\n")

        config_path = request.host_staging_dir / f"{request.job_id}.wsb"
        config_path.write_text(self.render_wsb_xml(request), encoding="utf-8", newline="\n")

        sentinel_path = request.host_results_dir / "job.completed.json"
        if sentinel_path.exists():
            sentinel_path.unlink()

        return config_path, command_path, sentinel_path

    def _summary(self, request: SandboxJobRequest, config_path: Path, command_path: Path, sentinel_path: Path) -> dict:
        return {
            "networking": request.networking_enabled,
            "clipboard": request.clipboard_enabled,
            "vgpu": request.vgpu_enabled,
            "printer_redirection": request.printer_redirection_enabled,
            "audio_input": request.audio_input_enabled,
            "video_input": request.video_input_enabled,
            "timeout_seconds": request.timeout_seconds,
            "staging_dir": str(request.host_staging_dir),
            "results_dir": str(request.host_results_dir),
            "config_path": str(config_path),
            "command_path": str(command_path),
            "sentinel_path": str(sentinel_path),
            "sandbox_folder_mappings": {
                "staging": {"read_only": True},
                "results": {"read_only": False},
            },
        }

    def run(self, request: SandboxJobRequest, *, dry_run: bool) -> SandboxRunResult:
        started = utcnow_iso()
        config_path, command_path, sentinel_path = self.stage_job(request)
        notes = [
            "networking-disabled-by-default" if not request.networking_enabled else "networking-enabled",
            "clipboard-disabled-by-default" if not request.clipboard_enabled else "clipboard-enabled",
            "vgpu-disabled-by-default" if not request.vgpu_enabled else "vgpu-enabled",
            "staging-read-only",
            "results-writable",
        ]
        summary = self._summary(request, config_path, command_path, sentinel_path)
        if dry_run:
            notes.append("dry-run")
            return SandboxRunResult(
                enabled=True,
                platform=self.platform,
                dry_run=True,
                config_path=str(config_path),
                command_path=str(command_path),
                sentinel_path=str(sentinel_path),
                started_at=started,
                ended_at=utcnow_iso(),
                exit_code=None,
                timed_out=False,
                artifacts_dir=str(request.host_results_dir),
                config_summary=summary,
                notes=notes,
            )

        if not self.sandbox_exe.exists():
            return SandboxRunResult(
                enabled=True,
                platform=self.platform,
                dry_run=False,
                config_path=str(config_path),
                command_path=str(command_path),
                sentinel_path=str(sentinel_path),
                started_at=started,
                ended_at=utcnow_iso(),
                exit_code=None,
                timed_out=False,
                artifacts_dir=str(request.host_results_dir),
                config_summary=summary,
                notes=notes + ["windows-sandbox-executable-not-found"],
            )

        proc = subprocess.Popen([str(self.sandbox_exe), str(config_path)])
        deadline = time.monotonic() + max(int(request.timeout_seconds), 1)
        timed_out = False
        exit_code = None
        try:
            while time.monotonic() < deadline:
                if sentinel_path.exists():
                    break
                time.sleep(0.5)
            else:
                timed_out = True
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
            if not timed_out:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    exit_code = None
            exit_code = proc.returncode if proc.returncode is not None else exit_code
        finally:
            ended = utcnow_iso()

        if sentinel_path.exists():
            try:
                import json

                sentinel_payload = json.loads(sentinel_path.read_text(encoding="utf-8"))
                if isinstance(sentinel_payload.get("exit_code"), int):
                    exit_code = sentinel_payload["exit_code"]
            except Exception:
                notes.append("sentinel-read-failed")

        if timed_out:
            notes.append("timed-out")

        return SandboxRunResult(
            enabled=True,
            platform=self.platform,
            dry_run=False,
            config_path=str(config_path),
            command_path=str(command_path),
            sentinel_path=str(sentinel_path),
            started_at=started,
            ended_at=ended,
            exit_code=exit_code,
            timed_out=timed_out,
            artifacts_dir=str(request.host_results_dir),
            config_summary=summary,
            notes=notes,
        )
