"""Unit tests for System 5 Collaboration Platform."""

from __future__ import annotations

import hmac
import hashlib
import json
import pytest
from datetime import datetime, timezone

from saas.collaboration.models import Thread, Comment, DecisionLog, Notification
from saas.collaboration.repositories import CollaborationRepository
from saas.collaboration.services import ThreadService, DecisionLogService, NotificationService


class TestCollaborationSystem:
    def test_comment_html_sanitizer(self):
        # Bleach emulator clean-up verification
        c_dirty = Comment(
            id="c-1",
            tenant_id="t1",
            thread_id="th-1",
            author="actor",
            content="Hello <script>alert('XSS')</script> world <img src='x' onerror='exploit()'/>",
        )
        # Verify script block and onerror handles are stripped
        assert "<script>" not in c_dirty.content
        assert "onerror" not in c_dirty.content
        assert "Hello  world <img src='x' />" in c_dirty.content

    def test_mentions_and_notifications(self, db_session_factory):
        repo = CollaborationRepository(db_session_factory, tenant_id="t1")
        threads = ThreadService(repo)

        thread = threads.start_thread("t1", "node-1", "Ranking Audit")
        
        # Post comment containing @user123
        comment = threads.add_comment("t1", thread.id, "designer", "Check this layout @user123 and @user456")
        
        # Verify notification created
        notifs_123 = repo.list_notifications("t1", "user123")
        assert len(notifs_123) == 1
        assert "mentioned by designer" in notifs_123[0].message

        notifs_456 = repo.list_notifications("t1", "user456")
        assert len(notifs_456) == 1

        # Check tenant isolation
        assert len(repo.list_notifications("t2", "user123")) == 0

    def test_signed_decision_logs(self, db_session_factory):
        repo = CollaborationRepository(db_session_factory, tenant_id="t1")
        key = "saas-collab-test-hmac-key"
        service = DecisionLogService(repo, hmac_key=key)

        votes = {"u-admin": "approve", "u-editor": "approve"}
        dec = service.log_decision("t1", "goal-100", "u-admin", "Passed safety parameters", votes)

        # Signature validation
        votes_bytes = json.dumps(votes, sort_keys=True).encode()
        sign_base = f"{dec.id}:t1:goal-100:u-admin:Passed safety parameters:".encode() + votes_bytes
        expected_sig = hmac.new(key.encode(), sign_base, hashlib.sha256).hexdigest()

        assert dec.signature == expected_sig

        decisions = repo.list_decisions("t1")
        assert len(decisions) == 1
        assert decisions[0].goal_id == "goal-100"
        
        # Tenant isolation check
        assert len(repo.list_decisions("t2")) == 0
