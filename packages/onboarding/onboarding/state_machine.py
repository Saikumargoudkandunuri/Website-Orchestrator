"""Onboarding state machine — the website onboarding lifecycle.

Tracks the ordered lifecycle a website moves through during onboarding
(architecture review #9 wizard + #10 digital-twin pipeline). The state machine
is the single authority on which transitions are legal, so services and routes
never guess.

States
------
``created``      -> website row exists, no connection yet
``connecting``   -> a connection is being established/verified
``verifying``    -> verification in progress
``detecting``    -> website detection in progress
``discovering``  -> integration discovery in progress
``crawling``     -> initial crawl in progress
``building``     -> digital twin build in progress
``ready``        -> fully onboarded, dashboard live
``error``        -> a step failed (recoverable; see ``last_error``)
``disabled``     -> administratively disabled

Transitions are validated; illegal transitions raise :class:`StateMachineError`.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.exceptions import OrchestratorError

__all__ = ["OnboardingState", "StateMachineError", "OnboardingStateMachine"]

#: The ordered happy-path lifecycle.
LIFECYCLE: tuple[str, ...] = (
    "created",
    "connecting",
    "verifying",
    "detecting",
    "discovering",
    "crawling",
    "building",
    "ready",
)


class StateMachineError(OrchestratorError):
    """Raised when an illegal onboarding state transition is requested."""


@dataclass(frozen=True)
class OnboardingState:
    """A single lifecycle state with its allowed forward/back transitions."""

    name: str
    allowed: frozenset[str]


class OnboardingStateMachine:
    """Validates and applies onboarding state transitions."""

    #: The legal transition graph. ``error`` and ``disabled`` are reachable from
    #: any active state; ``ready`` can return to ``crawling`` for a re-crawl.
    _GRAPH: dict[str, frozenset[str]] = {
        "created": frozenset({"connecting", "error", "disabled"}),
        "connecting": frozenset({"verifying", "error", "disabled"}),
        "verifying": frozenset({"detecting", "error", "disabled"}),
        "detecting": frozenset({"discovering", "error", "disabled"}),
        "discovering": frozenset({"crawling", "error", "disabled"}),
        "crawling": frozenset({"building", "error", "disabled"}),
        "building": frozenset({"ready", "error", "disabled"}),
        "ready": frozenset({"crawling", "error", "disabled"}),
        "error": frozenset(
            {"connecting", "verifying", "detecting", "crawling", "building", "ready", "disabled"}
        ),
        "disabled": frozenset({"created", "connecting"}),
    }

    @classmethod
    def is_valid(cls, current: str, target: str) -> bool:
        """Return ``True`` when ``target`` is a legal transition from ``current``."""
        allowed = cls._GRAPH.get(current)
        if allowed is None:
            return False
        return target in allowed

    @classmethod
    def transition(cls, current: str, target: str) -> str:
        """Validate and return ``target``; raise on an illegal transition."""
        if current == target:
            return target
        if not cls.is_valid(current, target):
            raise StateMachineError(
                f"Illegal onboarding transition: {current!r} -> {target!r}"
            )
        return target

    @classmethod
    def next(cls, current: str) -> str | None:
        """Return the next happy-path state after ``current``, or ``None``."""
        try:
            idx = LIFECYCLE.index(current)
        except ValueError:
            return None
        if idx + 1 >= len(LIFECYCLE):
            return None
        return LIFECYCLE[idx + 1]
