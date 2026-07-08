"""Shared session/tenant plumbing for intelligence repositories.

Mirrors the Digital_Twin repository's pattern: constructed with either an active
:class:`~sqlalchemy.orm.Session` (caller owns its lifecycle) or a session factory
(a fresh session per operation), and resolves the tenant to stamp from the call
argument or a configured default, rejecting a write with no resolvable tenant.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session, sessionmaker

from intelligence.errors import KnowledgeObjectError

__all__ = ["SessionMixin"]


class SessionMixin:
    """Provides ``_session()`` and ``_resolve_tenant()`` to a repository."""

    def __init__(
        self,
        session_source: Session | sessionmaker[Session] | object,
        *,
        tenant_id: str | None = None,
    ) -> None:
        self._session_source = session_source
        self._configured_tenant = tenant_id

    @contextmanager
    def _session(self) -> Iterator[Session]:
        external = isinstance(self._session_source, Session)
        session: Session = (
            self._session_source  # type: ignore[assignment]
            if external
            else self._session_source()  # type: ignore[operator]
        )
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            if not external:
                session.close()

    def _resolve_tenant(self, tenant_id: str | None) -> str:
        for candidate in (tenant_id, self._configured_tenant):
            if candidate is None:
                continue
            resolved = str(candidate).strip()
            if resolved:
                return resolved
        raise KnowledgeObjectError(
            "Cannot resolve a tenant_id for the write; refusing to persist a "
            "record without a tenant."
        )
