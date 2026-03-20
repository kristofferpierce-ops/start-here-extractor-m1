from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RetentionDecision:
    status: str
    retention_days: int
    legal_hold: bool
    review_after: str | None = None
    reason: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def derive_retention_decision(record: dict, *, retention_days: int = 30, legal_hold: bool = False, now: datetime | None = None) -> RetentionDecision:
    now = now or utcnow()
    if legal_hold:
        return RetentionDecision(status="held", retention_days=retention_days, legal_hold=True, review_after=None, reason="legal-hold")

    created = _parse_iso(record.get("generated_at") or ((record.get("run") or {}).get("ended_at") if isinstance(record.get("run"), dict) else None))
    if created is None:
        return RetentionDecision(status="active", retention_days=retention_days, legal_hold=False, review_after=None, reason="missing-timestamp")

    review_after = created + timedelta(days=retention_days)
    if now >= review_after:
        return RetentionDecision(status="review-due", retention_days=retention_days, legal_hold=False, review_after=review_after.isoformat(), reason="retention-window-reached")
    return RetentionDecision(status="active", retention_days=retention_days, legal_hold=False, review_after=review_after.isoformat(), reason="within-retention-window")
