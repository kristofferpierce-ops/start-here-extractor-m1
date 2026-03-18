from __future__ import annotations

from typing import Iterable, List, Sequence

from .errors import MultipleMatchesError, NoMatchError
from .types import Candidate, EntryInfo, MatchPolicy
from .utils import normalize_ext, normalize_name


def build_candidates(entries: Iterable[EntryInfo], policy: MatchPolicy) -> List[Candidate]:
    allowed_names = {normalize_name(name) for name in policy.allowed_basenames}
    allowed_exts = {ext.lower() for ext in policy.allowed_extensions}
    preferred_order = {ext.lower(): index for index, ext in enumerate(policy.preferred_extensions)}

    candidates: List[Candidate] = []
    for entry in entries:
        if entry.is_dir:
            continue
        normalized_name = normalize_name(entry.name)
        extension = normalize_ext(entry.name)
        if normalized_name not in allowed_names:
            continue
        if extension not in allowed_exts:
            continue
        priority = preferred_order.get(extension, 999)
        candidates.append(
            Candidate(
                name=entry.name,
                extension=extension,
                priority=priority,
                score_reason=f"normalized basename matched; extension {extension}",
                entry=entry,
            )
        )
    candidates.sort(key=lambda c: (c.priority, c.name.lower()))
    return candidates


def select_candidate(candidates: Sequence[Candidate], policy: MatchPolicy) -> Candidate:
    if not candidates:
        raise NoMatchError("No START HERE candidate matched the configured basenames and extensions")

    if len(candidates) == 1:
        return candidates[0]

    if policy.tie_policy == "error":
        names = ", ".join(candidate.name for candidate in candidates)
        raise MultipleMatchesError(f"Multiple matching candidates found: {names}")

    best_priority = candidates[0].priority
    best = [candidate for candidate in candidates if candidate.priority == best_priority]
    if len(best) == 1:
        return best[0]

    names = ", ".join(candidate.name for candidate in best)
    raise MultipleMatchesError(f"Multiple equally preferred candidates found: {names}")
