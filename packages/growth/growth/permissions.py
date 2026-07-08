"""Agency role permission matrix for Growth routes."""
from __future__ import annotations

from growth.agency_management.models import (
    PermissionAction,
    PermissionScope,
    RoleName,
)
from growth.auth import GrowthIdentity

__all__ = [
    "PermissionAction",
    "PermissionScope",
    "RoleName",
    "has_permission",
]


_ALL_ACTIONS = frozenset(PermissionAction)

_ROLE_MATRIX: dict[RoleName, dict[PermissionScope, frozenset[PermissionAction]]] = {
    RoleName.OWNER: {
        PermissionScope.ORGANIZATION: _ALL_ACTIONS,
        PermissionScope.CLIENT: _ALL_ACTIONS,
        PermissionScope.WORKSPACE: _ALL_ACTIONS,
    },
    RoleName.ADMIN: {
        PermissionScope.ORGANIZATION: _ALL_ACTIONS,
        PermissionScope.CLIENT: _ALL_ACTIONS,
        PermissionScope.WORKSPACE: _ALL_ACTIONS,
    },
    RoleName.MANAGER: {
        PermissionScope.ORGANIZATION: frozenset({
            PermissionAction.READ,
            PermissionAction.WRITE,
            PermissionAction.APPROVE,
        }),
        PermissionScope.CLIENT: frozenset({
            PermissionAction.READ,
            PermissionAction.WRITE,
            PermissionAction.APPROVE,
        }),
        PermissionScope.WORKSPACE: frozenset({
            PermissionAction.READ,
            PermissionAction.WRITE,
            PermissionAction.APPROVE,
        }),
    },
    RoleName.SEO_SPECIALIST: {
        PermissionScope.ORGANIZATION: frozenset({PermissionAction.READ}),
        PermissionScope.CLIENT: frozenset({
            PermissionAction.READ,
            PermissionAction.WRITE,
            PermissionAction.APPROVE,
        }),
        PermissionScope.WORKSPACE: frozenset({
            PermissionAction.READ,
            PermissionAction.WRITE,
            PermissionAction.APPROVE,
        }),
    },
    RoleName.CONTENT_WRITER: {
        PermissionScope.ORGANIZATION: frozenset({PermissionAction.READ}),
        PermissionScope.CLIENT: frozenset({
            PermissionAction.READ,
            PermissionAction.WRITE,
        }),
        PermissionScope.WORKSPACE: frozenset({
            PermissionAction.READ,
            PermissionAction.WRITE,
        }),
    },
    RoleName.CLIENT: {
        PermissionScope.ORGANIZATION: frozenset({PermissionAction.READ}),
        PermissionScope.CLIENT: frozenset({PermissionAction.READ}),
        PermissionScope.WORKSPACE: frozenset({PermissionAction.READ}),
    },
    RoleName.READ_ONLY: {
        PermissionScope.ORGANIZATION: frozenset({PermissionAction.READ}),
        PermissionScope.CLIENT: frozenset({PermissionAction.READ}),
        PermissionScope.WORKSPACE: frozenset({PermissionAction.READ}),
    },
}


def has_permission(
    identity: GrowthIdentity,
    action: PermissionAction,
    scope: PermissionScope,
) -> bool:
    """Return whether the identity can perform action at scope."""
    if action.value in identity.permissions:
        return True
    for role_value in identity.roles:
        try:
            role = RoleName(role_value)
        except ValueError:
            continue
        if action in _ROLE_MATRIX.get(role, {}).get(scope, frozenset()):
            return True
    return False
