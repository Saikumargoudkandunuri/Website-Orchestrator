"""Collaboration Services for System 5."""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from saas.collaboration.models import Thread, Comment, Notification, DecisionLog
from saas.collaboration.repositories import CollaborationRepository

__all__ = [
    "ThreadService",
    "NotificationService",
    "DecisionLogService",
]

logger = logging.getLogger(__name__)


class ThreadService:
    """Service governing discussion threads and commenting cycles."""

    def __init__(self, repo: CollaborationRepository) -> None:
        self._repo = repo

    def start_thread(self, tenant_id: str, node_id: str, title: str) -> Thread:
        thread = Thread(
            id=str(uuid4()),
            tenant_id=tenant_id,
            target_node_id=node_id,
            title=title,
        )
        self._repo.save_thread(thread)
        return thread

    def add_comment(self, tenant_id: str, thread_id: str, author: str, content: str) -> Comment:
        # Pydantic field validator handles the bleach/sanitize clean-up
        comment = Comment(
            id=str(uuid4()),
            tenant_id=tenant_id,
            thread_id=thread_id,
            author=author,
            content=content,
        )
        self._repo.save_comment(comment)
        
        # Scrape and record user mentions if any
        # e.g. text like "@user123 let's review" triggers a notify call
        if "@" in content:
            import re
            user_ids = re.findall(r"@(\w+)", content)
            for uid in user_ids:
                logger.info("Found mention for user %s inside comment %s", uid, comment.id)
                # Emit notification
                notif = Notification(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    user_id=uid,
                    message=f"You were mentioned by {author}: {content[:30]}...",
                )
                self._repo.save_notification(notif)

        return comment


class NotificationService:
    """Delivers real-time notifications to users."""

    def __init__(self, repo: CollaborationRepository) -> None:
        self._repo = repo

    def publish_notification(self, tenant_id: str, user_id: str, msg: str) -> Notification:
        notif = Notification(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            message=msg,
        )
        self._repo.save_notification(notif)
        return notif


class DecisionLogService:
    """Records cryptographically signed strategic workspace decisions."""

    def __init__(self, repo: CollaborationRepository, hmac_key: str = "saas-collab-hmac-key") -> None:
        self._repo = repo
        self._hmac_key = hmac_key.encode()

    def log_decision(
        self, tenant_id: str, goal_id: str, actor: str, rationale: str, votes: dict[str, Any]
    ) -> DecisionLog:
        record_id = str(uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # Compile signature payload
        votes_bytes = json.dumps(votes, sort_keys=True).encode()
        sign_base = f"{record_id}:{tenant_id}:{goal_id}:{actor}:{rationale}:".encode() + votes_bytes
        sig = hmac.new(self._hmac_key, sign_base, hashlib.sha256).hexdigest()

        dec = DecisionLog(
            id=record_id,
            tenant_id=tenant_id,
            goal_id=goal_id,
            actor=actor,
            rationale=rationale,
            votes_json=votes,
            signature=sig,
            created_at=timestamp,
        )
        self._repo.save_decision(dec)
        return dec
