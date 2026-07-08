"""Deterministic text/structure extraction from crawled HTML (§4.6, §4.4).

Milestone 1's crawler stores a page's raw ``html`` but not its heading tree,
paragraphs, or plain text. These helpers extract those deterministically so the
observed content metrics (word/keyword density, headings, first paragraph,
readability) are computed from crawled text — never AI-estimated (acceptance #3).
"""

from __future__ import annotations

import re
from collections import Counter

from bs4 import BeautifulSoup

__all__ = [
    "ExtractedContent",
    "extract_content",
    "keyword_density",
    "flesch_reading_ease",
]

_PARSER = "lxml"
_STOP_WORDS = frozenset(
    "a an the and or but of to in on for with at by from as is are was were be been "
    "being this that these those it its it's you your we our they their he she his her "
    "i me my mine ours yours will would can could should have has had do does did not "
    "no yes if then else than so such into over under about".split()
)


class ExtractedContent:
    """Parsed, deterministic view of a page's textual structure."""

    __slots__ = ("text", "headings", "paragraphs", "words")

    def __init__(
        self,
        text: str,
        headings: list[tuple[int, str]],
        paragraphs: list[str],
        words: list[str],
    ) -> None:
        self.text = text
        self.headings = headings  # [(level, text)]
        self.paragraphs = paragraphs
        self.words = words


def extract_content(html: str) -> ExtractedContent:
    """Extract plain text, heading tree, and paragraphs from ``html``."""
    if not html:
        return ExtractedContent("", [], [], [])
    soup = BeautifulSoup(html, _PARSER)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    headings: list[tuple[int, str]] = []
    for level in range(1, 7):
        for node in soup.find_all(f"h{level}"):
            heading_text = node.get_text(" ", strip=True)
            if heading_text:
                headings.append((level, heading_text))

    paragraphs = [
        p.get_text(" ", strip=True)
        for p in soup.find_all("p")
        if p.get_text(strip=True)
    ]

    text = soup.get_text(" ", strip=True)
    words = _tokenize(text)
    return ExtractedContent(text=text, headings=headings, paragraphs=paragraphs, words=words)


def keyword_density(words: list[str], *, top: int = 20) -> dict[str, float]:
    """Return the density (fraction of total words) of the top content words."""
    content = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    total = len(words) or 1
    counts = Counter(content)
    return {word: round(count / total, 4) for word, count in counts.most_common(top)}


def flesch_reading_ease(text: str) -> float | None:
    """Compute the Flesch Reading Ease score (higher = easier). ``None`` if empty."""
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    words = _tokenize(text)
    if not sentences or not words:
        return None
    syllables = sum(_count_syllables(w) for w in words)
    words_per_sentence = len(words) / len(sentences)
    syllables_per_word = syllables / len(words)
    score = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word
    return round(score, 2)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def _count_syllables(word: str) -> int:
    word = word.lower().strip("'")
    if not word:
        return 0
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)
