"""API_Surface subsystem — the FastAPI application and composition root.

Exposes the crawl, review, approval, and rollback loop over HTTP with automatic
OpenAPI docs. Thin route handlers delegate all business logic to the
subsystems. As the composition root, this is the only package that depends on
concrete subsystem packages in addition to Core_Package.
"""

from api.app import create_app

__all__: list[str] = ["create_app"]
