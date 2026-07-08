"""Root pytest configuration for the Website Orchestrator workspace.

Registers Hypothesis profiles for the whole monorepo. Every design correctness
property is implemented as a Hypothesis property-based test that must run a
minimum of 100 examples, so the default profile sets ``max_examples`` to 100.
Select a heavier profile with ``HYPOTHESIS_PROFILE=ci`` (or ``thorough``).
"""

from __future__ import annotations

import os

from hypothesis import settings

# Minimum required by the design: >= 100 examples per property.
settings.register_profile("default", max_examples=100, deadline=None)

# Heavier profiles for CI / release verification.
settings.register_profile("ci", max_examples=200, deadline=None)
settings.register_profile("thorough", max_examples=1000, deadline=None)

# Fast profile for quick local iteration (never used to certify a property).
settings.register_profile("dev", max_examples=25, deadline=None)

settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))
