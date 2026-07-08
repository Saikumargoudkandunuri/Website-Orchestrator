"""Deterministic, network-free SEO data provider test doubles (§8).

``FakeCompetitorDataProvider`` and ``FakeBacklinkDataProvider`` implement the
provider protocols with canned, configurable responses so every engine service
test is hermetic.  Swapping these for a second differently-behaved fake proves
the engines depend only on the protocol, not any concrete provider — satisfying
acceptance criterion #3.
"""

from __future__ import annotations

from core.results import Err, Ok, Result
from engines.errors import EngineDataProviderError
from engines.shared.provider_abstraction.seo_data_provider_interface import (
    BacklinkRecord,
    CompetitorBacklink,
    CompetitorKeyword,
    CompetitorPage,
    ReferringDomain,
)

__all__ = [
    "FakeCompetitorDataProvider",
    "FakeBacklinkDataProvider",
    "AlternativeFakeCompetitorDataProvider",
    "AlternativeFakeBacklinkDataProvider",
]


class FakeCompetitorDataProvider:
    """Default test double — returns minimal canned data."""

    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[tuple[str, str]] = []

    def fetch_competitor_pages(
        self, competitor_domain: str, topic: str
    ) -> Result[list[CompetitorPage], EngineDataProviderError]:
        self.calls.append(("pages", competitor_domain))
        if self._fail:
            return Err(EngineDataProviderError("fake competitor provider forced failure"))
        return Ok([
            CompetitorPage(
                url=f"https://{competitor_domain}/{topic}",
                title=f"{topic.title()} guide",
                estimated_traffic=1000.0,
                ranking_keywords=[topic, f"best {topic}"],
            )
        ])

    def fetch_competitor_keywords(
        self, competitor_domain: str
    ) -> Result[list[CompetitorKeyword], EngineDataProviderError]:
        self.calls.append(("keywords", competitor_domain))
        if self._fail:
            return Err(EngineDataProviderError("fake competitor provider forced failure"))
        return Ok([
            CompetitorKeyword(
                keyword="competitor keyword",
                competitor_position=3,
                our_position=None,
                estimated_volume=500.0,
                difficulty=0.6,
            )
        ])

    def fetch_competitor_backlinks(
        self, competitor_domain: str
    ) -> Result[list[CompetitorBacklink], EngineDataProviderError]:
        self.calls.append(("backlinks", competitor_domain))
        if self._fail:
            return Err(EngineDataProviderError("fake competitor provider forced failure"))
        return Ok([
            CompetitorBacklink(
                source_url="https://authority.example/article",
                target_url=f"https://{competitor_domain}/",
                anchor_text="competitor brand",
                domain_authority=60.0,
            )
        ])

    def name(self) -> str:
        return "fake_competitor"


class FakeBacklinkDataProvider:
    """Default test double for backlink data."""

    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[str] = []

    def fetch_backlinks(
        self, domain: str
    ) -> Result[list[BacklinkRecord], EngineDataProviderError]:
        self.calls.append(domain)
        if self._fail:
            return Err(EngineDataProviderError("fake backlink provider forced failure"))
        return Ok([
            BacklinkRecord(
                source_url="https://authority.example/post",
                target_url=f"https://{domain}/",
                anchor_text="brand name",
                first_seen="2024-01-01",
                last_seen="2024-06-01",
                link_type="dofollow",
                domain_authority=55.0,
            )
        ])

    def fetch_referring_domains(
        self, domain: str
    ) -> Result[list[ReferringDomain], EngineDataProviderError]:
        self.calls.append(domain)
        if self._fail:
            return Err(EngineDataProviderError("fake backlink provider forced failure"))
        return Ok([
            ReferringDomain(
                domain="authority.example",
                backlink_count=3,
                authority_score=55.0,
                first_seen="2024-01-01",
                is_toxic=False,
            )
        ])

    def name(self) -> str:
        return "fake_backlink"


# --- Alternative fakes for provider-swap acceptance test (#3) ----------------

class AlternativeFakeCompetitorDataProvider:
    """A differently-behaved competitor fake for provider-swap acceptance tests."""

    def fetch_competitor_pages(self, competitor_domain, topic):
        return Ok([
            CompetitorPage(url=f"https://{competitor_domain}/alt/{topic}", title="Alt page")
        ])

    def fetch_competitor_keywords(self, competitor_domain):
        return Ok([CompetitorKeyword(keyword="alt keyword", competitor_position=1)])

    def fetch_competitor_backlinks(self, competitor_domain):
        return Ok([])

    def name(self) -> str:
        return "alternative_fake_competitor"


class AlternativeFakeBacklinkDataProvider:
    """A differently-behaved backlink fake for provider-swap acceptance tests."""

    def fetch_backlinks(self, domain):
        return Ok([
            BacklinkRecord(
                source_url="https://alt.example/page",
                target_url=f"https://{domain}/page",
                link_type="nofollow",
            )
        ])

    def fetch_referring_domains(self, domain):
        return Ok([ReferringDomain(domain="alt.example", backlink_count=1)])

    def name(self) -> str:
        return "alternative_fake_backlink"
