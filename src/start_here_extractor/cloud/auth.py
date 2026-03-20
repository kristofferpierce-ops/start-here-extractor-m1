from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Protocol, TypeVar

from ..errors import RemoteAuthError, TokenResolutionError

CommandRunner = Callable[[str], subprocess.CompletedProcess[str]]
T = TypeVar("T")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass(frozen=True)
class ResolvedAccessToken:
    token: str
    source: str
    expires_at: str | None = None
    status: str = "provided"
    notes: list[str] | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        if payload["notes"] is None:
            payload["notes"] = []
        return payload

    def to_public_dict(self) -> dict:
        payload = self.to_dict()
        payload.pop("token", None)
        return payload


class AccessTokenProvider(Protocol):
    refreshable: bool

    def get_token(self, *, force_refresh: bool = False) -> str:
        raise NotImplementedError

    def get_resolved_token(self, *, force_refresh: bool = False) -> ResolvedAccessToken:
        raise NotImplementedError

    def public_state(self) -> dict[str, object]:
        raise NotImplementedError


def _default_command_runner(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)


def _parse_token_command_stdout(stdout: str) -> tuple[str, str | None, str | None, list[str] | None]:
    text = stdout.strip()
    if not text:
        return "", None, None, None

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        return first_line, None, None, None

    if not isinstance(value, dict):
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        return first_line, None, None, None

    token = str(value.get("access_token") or value.get("token") or "").strip()
    expires_at = value.get("expires_at") or value.get("expiry") or value.get("expires")
    source = value.get("source")
    notes = value.get("notes")
    return (
        token,
        str(expires_at) if expires_at else None,
        str(source) if source else None,
        [str(note) for note in notes] if isinstance(notes, list) else None,
    )


def _evaluate_token_status(*, expires_at: str | None, min_valid_seconds: int, extra_notes: list[str] | None = None) -> tuple[str, list[str]]:
    notes: list[str] = list(extra_notes or [])
    status = "provided"
    exp = _parse_iso(expires_at)
    if exp is not None:
        now = datetime.now(timezone.utc)
        if exp <= now:
            status = "expired"
            if "token-expired" not in notes:
                notes.append("token-expired")
        elif exp <= now + timedelta(seconds=min_valid_seconds):
            status = "stale"
            if "token-near-expiry" not in notes:
                notes.append("token-near-expiry")
        else:
            status = "fresh"
    return status, notes


def resolve_access_token(
    *,
    access_token: str | None = None,
    access_token_command: str | None = None,
    expires_at: str | None = None,
    min_valid_seconds: int = 300,
    command_runner: CommandRunner | None = None,
) -> ResolvedAccessToken:
    token = (access_token or "").strip()
    source = "argument"
    notes: list[str] = []
    effective_expires_at = expires_at

    if not token and access_token_command:
        runner = command_runner or _default_command_runner
        proc = runner(access_token_command)
        if proc.returncode != 0:
            raise TokenResolutionError(f"token-command-failed:{proc.returncode}")
        token, parsed_expires_at, parsed_source, parsed_notes = _parse_token_command_stdout(proc.stdout)
        source = parsed_source or "command"
        effective_expires_at = effective_expires_at or parsed_expires_at
        if parsed_notes:
            notes.extend(parsed_notes)

    if not token:
        raise TokenResolutionError("missing-cloud-access-token")

    status, evaluated_notes = _evaluate_token_status(
        expires_at=effective_expires_at,
        min_valid_seconds=min_valid_seconds,
        extra_notes=notes,
    )
    return ResolvedAccessToken(
        token=token,
        source=source,
        expires_at=effective_expires_at,
        status=status,
        notes=evaluated_notes,
    )


@dataclass
class StaticAccessTokenProvider:
    resolved: ResolvedAccessToken
    refreshable: bool = False

    def get_resolved_token(self, *, force_refresh: bool = False) -> ResolvedAccessToken:
        return self.resolved

    def get_token(self, *, force_refresh: bool = False) -> str:
        return self.resolved.token

    def public_state(self) -> dict[str, object]:
        payload = self.resolved.to_public_dict()
        payload["resolution_mode"] = "static"
        payload["refresh_count"] = 0
        payload["resolved_at"] = None
        return payload


@dataclass
class CommandAccessTokenProvider:
    access_token_command: str
    expires_at: str | None = None
    min_valid_seconds: int = 300
    command_runner: CommandRunner | None = None
    refreshable: bool = True
    _cached: ResolvedAccessToken | None = None
    _resolved_at: str | None = None
    _refresh_count: int = 0

    def _needs_refresh(self, *, force_refresh: bool) -> bool:
        if self._cached is None:
            return True
        if force_refresh:
            return True
        return self._cached.status in {"expired", "stale"}

    def _refresh(self) -> ResolvedAccessToken:
        had_cached = self._cached is not None
        resolved = resolve_access_token(
            access_token_command=self.access_token_command,
            expires_at=self.expires_at,
            min_valid_seconds=self.min_valid_seconds,
            command_runner=self.command_runner,
        )
        self._cached = resolved
        self._resolved_at = _utcnow_iso()
        if had_cached:
            self._refresh_count += 1
        return resolved

    def get_resolved_token(self, *, force_refresh: bool = False) -> ResolvedAccessToken:
        if self._needs_refresh(force_refresh=force_refresh):
            return self._refresh()
        assert self._cached is not None
        return self._cached

    def get_token(self, *, force_refresh: bool = False) -> str:
        return self.get_resolved_token(force_refresh=force_refresh).token

    def public_state(self) -> dict[str, object]:
        resolved = self.get_resolved_token()
        payload = resolved.to_public_dict()
        payload["resolution_mode"] = "command"
        payload["refresh_count"] = self._refresh_count
        payload["resolved_at"] = self._resolved_at
        return payload


def build_access_token_provider(
    *,
    access_token: str | None = None,
    access_token_command: str | None = None,
    expires_at: str | None = None,
    min_valid_seconds: int = 300,
    command_runner: CommandRunner | None = None,
) -> AccessTokenProvider:
    token = (access_token or "").strip()
    if token:
        return StaticAccessTokenProvider(
            resolve_access_token(
                access_token=token,
                expires_at=expires_at,
                min_valid_seconds=min_valid_seconds,
                command_runner=command_runner,
            )
        )
    if access_token_command:
        return CommandAccessTokenProvider(
            access_token_command=access_token_command,
            expires_at=expires_at,
            min_valid_seconds=min_valid_seconds,
            command_runner=command_runner,
        )
    raise TokenResolutionError("missing-cloud-access-token")


def run_with_auth_retry(action: Callable[[], T], provider: AccessTokenProvider | None = None) -> T:
    try:
        return action()
    except RemoteAuthError:
        if provider is None or not provider.refreshable:
            raise
        provider.get_token(force_refresh=True)
        return action()
