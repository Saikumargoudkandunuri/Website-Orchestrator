"""Unit tests for System 2 Enterprise SaaS Platform."""

from __future__ import annotations

import hmac
import hashlib
import json
import pytest
from datetime import datetime, timezone

from saas.enterprise.models import UserRoleAssignment, AuditTrailRecord
from saas.enterprise.repositories import EnterpriseRepository
from saas.enterprise.services import (
    AccessControlService,
    UsageMeterService,
    AuditLogService,
    StripeService,
)


class TestEnterpriseSystem:
    def test_access_control_rbac(self, db_session_factory):
        repo = EnterpriseRepository(db_session_factory, tenant_id="t1")
        rbac = AccessControlService(repo)

        # Assign user_admin as admin, user_reader as reader
        from uuid import uuid4
        repo.save_role(UserRoleAssignment(id=str(uuid4()), tenant_id="t1", user_id="u-admin", role="admin"))
        repo.save_role(UserRoleAssignment(id=str(uuid4()), tenant_id="t1", user_id="u-read", role="reader"))

        # Permissions check
        assert rbac.has_permission("t1", "u-admin", "publish") is True
        assert rbac.has_permission("t1", "u-read", "publish") is False
        assert rbac.has_permission("t1", "u-read", "read") is True
        # Unknown user has no permission
        assert rbac.has_permission("t1", "u-unknown", "read") is False

    def test_usage_meter_limits(self):
        meter = UsageMeterService(quota_limit=10)
        
        # Increment usage
        assert meter.record_usage("t1", 8) is True
        assert meter.record_usage("t1", 3) is False  # exceeds quota limit 10
        assert meter.get_usage("t1") == 8

    def test_signed_audit_logs(self, db_session_factory):
        repo = EnterpriseRepository(db_session_factory, tenant_id="t1")
        key = "test-hmac-secret-key"
        service = AuditLogService(repo, hmac_key=key)

        changes = {"name": "Old Workspace", "new_name": "Audited Workspace"}
        record = service.log_action("t1", "actor-123", "rename_workspace", "ws-456", changes)

        # Verify signature matching
        payload_bytes = json.dumps(changes, sort_keys=True).encode()
        sign_base = f"{record.id}:t1:actor-123:rename_workspace:ws-456:".encode() + payload_bytes
        expected_sig = hmac.new(key.encode(), sign_base, hashlib.sha256).hexdigest()

        assert record.signature == expected_sig

        # Retrieve and verify tenant isolation
        audits = repo.list_audits("t1")
        assert len(audits) == 1
        assert audits[0].actor == "actor-123"

        # Separate tenant has no audit entries
        assert len(repo.list_audits("t2")) == 0

    def test_stripe_subscription_webhook(self):
        service = StripeService()
        sub = service.create_mock_subscription("org-1", "growth")
        assert sub.status == "active"

        # Trigger subscription cancelled webhook event
        res = service.handle_webhook_event("customer.subscription.deleted", {"id": sub.stripe_sub_id})
        assert res is True
        assert sub.status == "canceled"
