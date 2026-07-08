"""Brain — Milestone 5 Unified Intelligence Layer.

Provides the cross-engine synthesis layer (``SeoBrain``) and the shared
Website Knowledge Graph substrate. Depends on M2 Intelligence, M3 Engines,
and M4 Growth — read-only on all. No engine or Growth module may depend on
``brain/`` — strictly one-directional.
"""

from brain.models import SiteSynthesis
from brain.services import SeoBrain

__all__ = [
    "SiteSynthesis",
    "SeoBrain",
]
