"""Automation Engine interface (§4.10)."""
from __future__ import annotations

__all__ = ["AutomationEngine"]


class AutomationEngine:
    """
    Cross-cutting Automation Engine (§4.10).
    
    NOT an analytical or generator engine - it's CRUD-oriented for AutomationRule entities.
    The actual rule execution happens via EventBus subscription in AutomationService.
    """
    
    engine_name = "automation"
    engine_version = "1.0.0"
    
    # No analyze() or generate() - this engine is event-driven
    # Rules are managed via CRUD API, execution is triggered by events
