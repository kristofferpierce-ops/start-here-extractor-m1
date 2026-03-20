from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .errors import AuthorizationError

DEFAULT_ROLE_ACTIONS: dict[str, set[str]] = {
    "viewer": set(),
    "analyst": {"playbook.run.dry_run"},
    "operator": {"playbook.run", "playbook.run.dry_run"},
    "admin": {"playbook.run", "playbook.run.dry_run", "playbook.configure", "playbook.override"},
}


@dataclass(slots=True)
class Principal:
    actor_id: str
    roles: list[str] = field(default_factory=list)
    allowed_actions: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, object]:
        return {
            "actor_id": self.actor_id,
            "roles": list(self.roles),
            "allowed_actions": sorted(self.allowed_actions),
        }


def expand_actions(roles: Iterable[str], role_actions: Mapping[str, Iterable[str]] | None = None) -> set[str]:
    role_actions = role_actions or DEFAULT_ROLE_ACTIONS
    allowed: set[str] = set()
    for role in roles:
        allowed.update(str(item) for item in role_actions.get(str(role), []))
    return allowed


def build_principal(actor_id: str, roles: Iterable[str], *, role_actions: Mapping[str, Iterable[str]] | None = None) -> Principal:
    role_list = [str(role) for role in roles]
    return Principal(actor_id=str(actor_id), roles=role_list, allowed_actions=expand_actions(role_list, role_actions))


def require_action(principal: Principal, action: str) -> None:
    if action not in principal.allowed_actions:
        raise AuthorizationError(f"actor {principal.actor_id} lacks permission: {action}")
