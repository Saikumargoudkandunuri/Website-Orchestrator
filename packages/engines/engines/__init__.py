"""Engines subsystem — Milestone 3 enterprise SEO intelligence engines.

Ten independently-structured engines that collectively exceed the scope of
SEMrush, Ahrefs, Moz, Screaming Frog, and similar tools. Each engine:
- Implements the shared :class:`~engines.shared.Engine` protocol.
- Has an identical internal folder structure (models, interfaces, services,
  repositories, api).
- Persists typed, versioned, append-only output on its own SQLAlchemy tables.
- Never calls another engine's service layer directly.
- Is fully unit-testable with zero real AI or third-party provider calls.

Depends on wo-core and wo-intelligence (Milestone 2). Additive only — M1/M2 are
never modified.
"""

__all__: list[str] = []
