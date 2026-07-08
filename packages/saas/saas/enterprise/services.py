"""Enterprise Services for System 2."""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from saas.enterprise.models import (
    Organization,
    Subscription,
    AuditTrailRecord,
    UserRoleAssignment,
)

__all__ = [
    "AccessControlService",
    "UsageMeterService",
    "AuditLogService",
    "StripeService",
]

logger = logging.getLogger(__name__)


class AccessControlService:
    """Enterprise Access Control mapping (RBAC)."""

    def __init__(self, role_repo: Any) -> None:
        self._repo = role_repo
        # Permission matrix mapping role -> list of permitted actions
        self._matrix = {
            "admin": {"read", "write", "publish", "delete"},
            "writer": {"read", "write"},
            "reader": {"read"},
        }

    def has_permission(self, tenant_id: str, user_id: str, action: str) -> bool:
        """Resolve tenant user assignments and verify authorization."""
        # Query role mapping from DB
        role = self._repo.get_user_role(tenant_id, user_id)
        if not role:
            return False
        allowed = self._matrix.get(role, set())
        return action in allowed


class UsageMeterService:
    """Usage metering engine."""

    def __init__(self, quota_limit: int = 1000) -> None:
        self._limit = quota_limit
        # In-memory accumulator for simple checks
        self._usage: dict[str, int] = {}

    def record_usage(self, tenant_id: str, amount: int = 1) -> bool:
        """Accumulate usage. Returns False if monthly quota limit exceeded."""
        current = self._usage.get(tenant_id, 0)
        if current + amount > self._limit:
            return False
        self._usage[tenant_id] = current + amount
        return True

    def get_usage(self, tenant_id: str) -> int:
        return self._usage.get(tenant_id, 0)


class AuditLogService:
    """Audit Logging Service using HMAC keys for verification."""

    def __init__(self, audit_repo: Any, hmac_key: str = "secret-hmac-key") -> None:
        self._repo = audit_repo
        self._hmac_key = hmac_key.encode()

    def log_action(
        self, tenant_id: str, actor: str, action: str, target_id: str, changes: dict[str, Any]
    ) -> AuditTrailRecord:
        """Generate a cryptographically signed audit trail record."""
        record_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Serialize changes payload to bytes for signature
        payload_bytes = json.dumps(changes, sort_keys=True).encode()
        sign_base = f"{record_id}:{tenant_id}:{actor}:{action}:{target_id}:".encode() + payload_bytes
        
        sig = hmac.new(self._hmac_key, sign_base, hashlib.sha256).hexdigest()

        record = AuditTrailRecord(
            id=record_id,
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            target_id=target_id,
            changes_json=changes,
            signature=sig,
            created_at=timestamp,
        )
        self._repo.save_audit(record)
        return record


class StripeService:
    """Stripe Billing integration service wrapper."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, Subscription] = {}

    def create_mock_subscription(self, org_id: str, plan_tier: str) -> Subscription:
        sub = Subscription(
            id=str(uuid4()),
            org_id=org_id,
            stripe_sub_id=f"sub_{str(uuid4())[:8]}",
            plan_tier=plan_tier,
            status="active",
            current_period_end=datetime.now(timezone.utc),
        )
        self._subscriptions[sub.stripe_sub_id] = sub
        return sub

    def handle_webhook_event(self, event_type: str, data: dict[str, Any]) -> bool:
        """Process incoming events."""
        if event_type == "customer.subscription.deleted":
            sub_id = data.get("id")
            if sub_id in self._subscriptions:
                self._subscriptions[sub_id].status = "canceled"
                return True
        return False
