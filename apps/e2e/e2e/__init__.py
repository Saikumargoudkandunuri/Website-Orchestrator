"""End-to-end proof of the loop (Requirement 11).

Exercises the full Observe -> Execute -> Verify loop against a local
Fixture_Site, a local PostgreSQL datastore, and a mocked WordPress client so no
request leaves localhost and no real credential is used.
"""

__all__: list[str] = []
