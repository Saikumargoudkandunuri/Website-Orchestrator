"""Intelligence subsystem — the Milestone 2 SEO Intelligence Layer.

Adds a persistent, versioned per-page "SEO Knowledge Object", a
provider-agnostic AI layer, a reusable prompt/validation pipeline, and analyzer
services that deepen the system's *understanding* of each page. It is purely
additive: it depends on Core_Package (and reads Milestone 1's typed records) but
nothing in Milestone 0/1 depends on it. Milestone 2 never mutates the live site
— proposals flow through Milestone 1's existing Governance/Publisher pipeline.
"""

__all__: list[str] = []
