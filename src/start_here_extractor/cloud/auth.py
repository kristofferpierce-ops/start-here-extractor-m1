from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from ..errors import TokenResolutionError


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


def resolve_access_token(*, access_token: str | None = None, access_token_command: str | None = None, expires_at: str | None = None, min_valid_seconds: int = 300) -> ResolvedAccessToken:
    token = (access_token or "").strip()
    source = "argument"
    if not token and access_token_command:
        proc = subprocess.run(access_token_command, shell=True, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            raise TokenResolutionError(f"token-command-failed:{proc.returncode}")
        token = next((line.strip() for line in proc.stdout.splitlines() if line.strip()), "")
        source = "command"
    if not token:
        raise TokenResolutionError("missing-cloud-access-token")

    notes: list[str] = []
    status = "provided"
    exp = _parse_iso(expires_at)
    if exp is not None:
        now = datetime.now(timezone.utc)
        if exp <= now:
            status = "expired"
            notes.append("token-expired")
        elif exp <= now + timedelta(seconds=min_valid_seconds):
            status = "stale"
            notes.append("token-near-expiry")
        else:
            status = "fresh"
    return ResolvedAccessToken(token=token, source=source, expires_at=expires_at, status=status, notes=notes)
