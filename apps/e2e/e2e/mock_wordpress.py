"""In-memory mocked WordPress client for the end-to-end proof (Req 11.2).

The Requirement 11 end-to-end proof stands a **mocked WordPress client** in
place of the live Publishing_Adapter target (Req 11.2), so the loop can be
driven to completion without contacting a live site or using a real credential
(Req 11.1). :class:`MockWordPressClient` implements the full
:class:`~core.interfaces.PublishingAdapterPort` contract
(``list_pages``/``get_page``/``update_page_content``/``get_media``/
``update_media_alt_text``) over in-memory dictionaries.

It is also a **spy**: every read and every write is recorded so tests can assert
call counts and ordering — e.g. that approving an Auto_Applicable_Fix causes
*exactly one* write (Req 11.5), that reading back returns the written value
(Req 11.6), and that approving a Report_Only_Fix causes *no* write (Req 11.7).

No credential is ever involved. The client holds no ``Application_Password`` and
opens no connection; it is constructed with a seed of pages/media and mutates
that seed in place. This satisfies the "no real WordPress credential is used"
constraint (Req 11.2) structurally — there is no credential to use.

Reads for an unknown id raise :class:`~core.exceptions.WPNotFoundError` (the same
typed error the real adapter raises, Req 7.3) so callers that depend on the Port
contract behave identically against the mock.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.exceptions import WPNotFoundError
from core.interfaces import WPMedia, WPPage

__all__ = ["MockWordPressClient", "WriteRecord", "ReadRecord"]


@dataclass(frozen=True)
class ReadRecord:
    """One recorded read against the mock client (spy entry)."""

    op: str  # "list_pages" | "get_page" | "get_media"
    target_id: int | None  # page/media id, or None for list_pages


@dataclass(frozen=True)
class WriteRecord:
    """One recorded write against the mock client (spy entry)."""

    op: str  # "update_page_content" | "update_media_alt_text"
    target_id: int  # page/media id written to
    value: str  # the value written (content or alt_text)


@dataclass
class MockWordPressClient:
    """An in-memory :class:`~core.interfaces.PublishingAdapterPort` spy (Req 11.2).

    Parameters
    ----------
    pages:
        Seed mapping of page id -> :class:`~core.interfaces.WPPage`.
    media:
        Seed mapping of media id -> :class:`~core.interfaces.WPMedia`.

    The client records every read in :attr:`reads` and every write in
    :attr:`writes`, in call order, so tests can assert exact read/write activity
    (Req 11.5-11.7). :attr:`write_count` / :attr:`read_count` are convenience
    accessors over those logs.
    """

    pages: dict[int, WPPage] = field(default_factory=dict)
    media: dict[int, WPMedia] = field(default_factory=dict)
    reads: list[ReadRecord] = field(default_factory=list)
    writes: list[WriteRecord] = field(default_factory=list)

    # --- Read side (PublishingAdapterPort) -----------------------------------

    def list_pages(self) -> list[WPPage]:
        """Return all seeded pages, recording the read (Req 6.1)."""
        self.reads.append(ReadRecord(op="list_pages", target_id=None))
        return list(self.pages.values())

    def get_page(self, page_id: int) -> WPPage:
        """Return the page ``page_id`` or raise ``WPNotFoundError`` (Req 6.1, 7.3)."""
        self.reads.append(ReadRecord(op="get_page", target_id=page_id))
        page = self.pages.get(page_id)
        if page is None:
            raise WPNotFoundError(f"No WordPress page with id {page_id}.")
        return page

    def get_media(self, media_id: int) -> WPMedia:
        """Return the media ``media_id`` or raise ``WPNotFoundError`` (Req 6.1, 7.3)."""
        self.reads.append(ReadRecord(op="get_media", target_id=media_id))
        item = self.media.get(media_id)
        if item is None:
            raise WPNotFoundError(f"No WordPress media with id {media_id}.")
        return item

    # --- Write side (PublishingAdapterPort) ----------------------------------

    def update_page_content(self, page_id: int, content: str) -> WPPage:
        """Write ``content`` to page ``page_id`` and return the updated record.

        Only the ``content`` field is written (Req 6.2). Repeated writes of the
        same value are idempotent — the stored state simply equals the target
        value (Req 7.7). The write is recorded in :attr:`writes`.
        """
        existing = self.pages.get(page_id)
        if existing is None:
            raise WPNotFoundError(f"No WordPress page with id {page_id}.")
        updated = existing.model_copy(update={"content": content})
        self.pages[page_id] = updated
        self.writes.append(
            WriteRecord(op="update_page_content", target_id=page_id, value=content)
        )
        return updated

    def update_media_alt_text(self, media_id: int, alt_text: str) -> WPMedia:
        """Write ``alt_text`` to media ``media_id`` and return the updated record.

        Only the ``alt_text`` field is written (Req 6.2); repeated identical
        writes are idempotent (Req 7.7). The write is recorded in :attr:`writes`.
        """
        existing = self.media.get(media_id)
        if existing is None:
            raise WPNotFoundError(f"No WordPress media with id {media_id}.")
        updated = existing.model_copy(update={"alt_text": alt_text})
        self.media[media_id] = updated
        self.writes.append(
            WriteRecord(
                op="update_media_alt_text", target_id=media_id, value=alt_text
            )
        )
        return updated

    # --- Spy conveniences -----------------------------------------------------

    @property
    def write_count(self) -> int:
        """Number of writes recorded so far."""
        return len(self.writes)

    @property
    def read_count(self) -> int:
        """Number of reads recorded so far."""
        return len(self.reads)

    def reset_spy(self) -> None:
        """Clear the recorded read/write logs without touching stored state.

        Useful in a multi-step end-to-end test to assert the write activity of a
        single step (e.g. one approval) in isolation.
        """
        self.reads.clear()
        self.writes.clear()
