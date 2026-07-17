"""Onboarding — the Foundation sub-project.

This package turns a brand-new Website Orchestrator installation into a fully
connected instance. It owns the workspace/project/website/connection data model
and the services that onboard a live website: detection, integration discovery,
initial crawl, and digital-twin bootstrapping.

It deliberately reuses the existing subsystem contracts (Crawler, Digital_Twin,
Publishing_Adapter, Editing) rather than re-implementing them.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
