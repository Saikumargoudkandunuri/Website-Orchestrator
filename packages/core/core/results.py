"""Core_Package result objects — typed success/failure and read outcomes.

Per Requirement 15.5, any operation that represents *success or a typed
failure* returns one of the Result Objects defined here rather than signalling
via ``None``, exceptions, or ad-hoc tuples. This gives every subsystem a single,
explicit, statically-typeable vocabulary for outcomes:

* :class:`Ok` — a successful outcome carrying a value.
* :class:`Err` — a failed outcome carrying a typed error.
* :data:`Result` — the union ``Ok[T] | Err[E]`` returned by fallible operations.

Reads from the Digital_Twin have a richer outcome space than plain
success/failure, so this module also defines two *read sentinels* that model the
"no usable data" cases explicitly (Req 3.4–3.6):

* :class:`NotFound` — the requested item is not stored at all.
* :class:`Stale` — the item exists but is older than the freshness threshold and
  must be re-crawled before it is used to act.

``Digital_Twin.get_page`` therefore returns :data:`ReadResult`, the union
``Ok[T] | NotFound | Stale``.

Per Requirement 15.2/15.6 this module imports nothing internal to the
orchestrator; it depends only on the standard library so the dependency
direction always points inward toward Core_Package.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Generic, TypeVar, Union

__all__ = [
    "Ok",
    "Err",
    "Result",
    "NotFound",
    "Stale",
    "ReadResult",
    "UnwrapError",
    "is_ok",
    "is_err",
]

#: Success value type.
T = TypeVar("T")
#: Error value type.
E = TypeVar("E")
#: Mapped success value type.
U = TypeVar("U")
#: Mapped error value type.
F = TypeVar("F")


class UnwrapError(Exception):
    """Raised when a Result is unwrapped against its actual variant.

    Analogous to a failed ``Result.unwrap`` in other ecosystems: it signals a
    programming error (the caller assumed a variant it did not check) rather than
    an anticipated, handled failure. Handled failures are represented as
    :class:`Err`, never by raising.
    """


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    """A successful outcome wrapping ``value``."""

    value: T

    @property
    def is_ok(self) -> bool:
        """Always ``True`` for :class:`Ok`."""
        return True

    @property
    def is_err(self) -> bool:
        """Always ``False`` for :class:`Ok`."""
        return False

    def unwrap(self) -> T:
        """Return the wrapped success value."""
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Return the wrapped value, ignoring ``default``."""
        return self.value

    def unwrap_err(self) -> Any:
        """Raise :class:`UnwrapError` — an :class:`Ok` has no error."""
        raise UnwrapError(f"Called unwrap_err on an Ok value: {self.value!r}")

    def map(self, fn: Callable[[T], U]) -> "Ok[U]":
        """Apply ``fn`` to the wrapped value, returning a new :class:`Ok`."""
        return Ok(fn(self.value))

    def map_err(self, fn: Callable[[Any], F]) -> "Ok[T]":
        """Return this :class:`Ok` unchanged; there is no error to map."""
        return self


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    """A failed outcome wrapping a typed ``error``."""

    error: E

    @property
    def is_ok(self) -> bool:
        """Always ``False`` for :class:`Err`."""
        return False

    @property
    def is_err(self) -> bool:
        """Always ``True`` for :class:`Err`."""
        return True

    def unwrap(self) -> Any:
        """Raise :class:`UnwrapError` — an :class:`Err` has no success value."""
        raise UnwrapError(f"Called unwrap on an Err value: {self.error!r}")

    def unwrap_or(self, default: U) -> U:
        """Return ``default`` since there is no success value."""
        return default

    def unwrap_err(self) -> E:
        """Return the wrapped error value."""
        return self.error

    def map(self, fn: Callable[[Any], U]) -> "Err[E]":
        """Return this :class:`Err` unchanged; there is no value to map."""
        return self

    def map_err(self, fn: Callable[[E], F]) -> "Err[F]":
        """Apply ``fn`` to the wrapped error, returning a new :class:`Err`."""
        return Err(fn(self.error))


#: The canonical fallible-operation outcome: success (:class:`Ok`) or a typed
#: failure (:class:`Err`).
Result = Union[Ok[T], Err[E]]


@dataclass(frozen=True, slots=True)
class NotFound:
    """Read sentinel: the requested item is not stored (Req 3.6).

    ``key`` optionally records what was looked up (for example the requested
    URL) so callers and logs can report the miss without a separate lookup.
    """

    key: str | None = None

    @property
    def is_ok(self) -> bool:
        """Always ``False`` — a read sentinel is not a success."""
        return False

    @property
    def is_err(self) -> bool:
        """Always ``False`` — a read sentinel is not a typed error."""
        return False


@dataclass(frozen=True, slots=True)
class Stale:
    """Read sentinel: the item exists but is too old to act on (Req 3.5).

    The stored data is deliberately withheld so callers cannot act on stale
    information; a re-crawl is required first. Context is carried for reporting:

    * ``key`` — what was requested (for example the page URL),
    * ``crawled_at`` — the UTC timestamp the stale data was last crawled,
    * ``age_seconds`` — optional elapsed age at read time,
    * ``threshold_seconds`` — optional configured staleness threshold.
    """

    key: str | None = None
    crawled_at: datetime | None = None
    age_seconds: float | None = None
    threshold_seconds: float | None = None

    @property
    def is_ok(self) -> bool:
        """Always ``False`` — a read sentinel is not a success."""
        return False

    @property
    def is_err(self) -> bool:
        """Always ``False`` — a read sentinel is not a typed error."""
        return False


#: A read outcome for freshness-aware reads such as ``Digital_Twin.get_page``:
#: a fresh hit (:class:`Ok`), a miss (:class:`NotFound`), or a stale hit
#: (:class:`Stale`).
ReadResult = Union[Ok[T], NotFound, Stale]


def is_ok(result: Any) -> bool:
    """Return ``True`` when ``result`` is an :class:`Ok`."""
    return isinstance(result, Ok)


def is_err(result: Any) -> bool:
    """Return ``True`` when ``result`` is an :class:`Err`."""
    return isinstance(result, Err)
