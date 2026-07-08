"""Deterministic, network-free growth data provider test doubles (§1.2, §10).

One module with all five fake provider implementations so tests are hermetic.
Swapping these for a second differently-behaved fake proves the engines depend
only on the protocol, not any concrete provider.
"""

from __future__ import annotations

from datetime import datetime, timezone

from core.results import Err, Ok, Result
from growth.errors import GrowthDataProviderError
from growth.shared.provider_abstraction.analytics_data_provider_interface import (
    AnalyticsSnapshot,
    TopKeyword,
    TopPage,
)
from growth.shared.provider_abstraction.local_seo_data_provider_interface import (
    BusinessProfileData,
    CitationRecord,
    DirectoryListing,
)
from growth.shared.provider_abstraction.outreach_data_provider_interface import (
    ContactRecord,
    DomainQualificationData,
)
from growth.shared.provider_abstraction.rank_tracking_provider_interface import (
    RankingSnapshot,
)
from growth.shared.provider_abstraction.reputation_data_provider_interface import (
    BrandMention,
    ReviewRecord,
)

__all__ = [
    "FakeLocalSeoDataProvider",
    "FakeReputationDataProvider",
    "FakeAnalyticsDataProvider",
    "FakeRankTrackingProvider",
    "FakeOutreachDataProvider",
]

_NOW = datetime(2024, 6, 1, tzinfo=timezone.utc)


class FakeLocalSeoDataProvider:
    """Default test double for local SEO data."""

    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[tuple[str, str]] = []

    def fetch_business_profile(
        self, location_id: str
    ) -> Result[BusinessProfileData, GrowthDataProviderError]:
        self.calls.append(("profile", location_id))
        if self._fail:
            return Err(GrowthDataProviderError("fake local SEO provider forced failure"))
        return Ok(BusinessProfileData(
            location_id=location_id,
            business_name="Acme Corp",
            address="123 Main St, Springfield",
            phone="+1-555-0100",
            website=f"https://acme.example/{location_id}",
            categories=["Restaurant", "Catering"],
            hours={"Monday": "9am-5pm", "Tuesday": "9am-5pm"},
            photo_count=5,
            post_count_last_30_days=2,
            rating=4.2,
            review_count=47,
            is_verified=True,
            data_source="fake_local_seo",
            data_completeness=0.7,
        ))

    def fetch_citations(
        self, location_id: str
    ) -> Result[list[CitationRecord], GrowthDataProviderError]:
        self.calls.append(("citations", location_id))
        if self._fail:
            return Err(GrowthDataProviderError("fake local SEO provider forced failure"))
        return Ok([
            CitationRecord(
                directory_name="Yelp",
                url=f"https://yelp.com/biz/{location_id}",
                business_name="Acme Corp",
                address="123 Main St",
                phone="+1-555-0100",
                is_claimed=True,
                is_accurate=True,
                data_source="fake_local_seo",
            ),
            CitationRecord(
                directory_name="Yellow Pages",
                url=None,
                business_name="Acme Corp",
                address="123 Main Street",  # intentional inconsistency for NAP test
                phone="+1-555-0101",  # different phone — NAP inconsistency
                is_claimed=False,
                is_accurate=False,
                data_source="fake_local_seo",
            ),
        ])

    def fetch_directory_listings(
        self, location_id: str
    ) -> Result[list[DirectoryListing], GrowthDataProviderError]:
        self.calls.append(("directories", location_id))
        if self._fail:
            return Err(GrowthDataProviderError("fake local SEO provider forced failure"))
        return Ok([
            DirectoryListing(
                directory_name="Google Business Profile",
                directory_url="https://business.google.com",
                is_listed=True,
                listing_url=f"https://g.page/{location_id}",
                status="listed",
                data_source="fake_local_seo",
            ),
            DirectoryListing(
                directory_name="Bing Places",
                directory_url="https://bingplaces.com",
                is_listed=False,
                status="missing",
                data_source="fake_local_seo",
            ),
        ])

    def name(self) -> str:
        return "fake_local_seo"


class FakeReputationDataProvider:
    """Default test double for reputation/review data."""

    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[tuple[str, str | None]] = []

    def fetch_reviews(
        self, site_id: str, location_id: str | None = None
    ) -> Result[list[ReviewRecord], GrowthDataProviderError]:
        self.calls.append(("reviews", location_id))
        if self._fail:
            return Err(GrowthDataProviderError("fake reputation provider forced failure"))
        return Ok([
            ReviewRecord(
                review_id="rev-001",
                platform="google",
                author_name="Alice Smith",
                rating=5.0,
                text="Excellent service! The team was professional and the results exceeded expectations.",
                date=_NOW,
                is_responded=False,
                location_id=location_id,
                data_source="fake_reputation",
                data_completeness=0.8,
            ),
            ReviewRecord(
                review_id="rev-002",
                platform="google",
                author_name="Bob Jones",
                rating=1.0,
                text="Terrible experience. The product broke after one week and customer service was unhelpful.",
                date=_NOW,
                is_responded=False,
                location_id=location_id,
                data_source="fake_reputation",
                data_completeness=0.8,
            ),
            ReviewRecord(
                review_id="rev-003",
                platform="trustpilot",
                author_name="Carol White",
                rating=4.0,
                text="Good overall but delivery was slow. Quality of the product itself is very good.",
                date=_NOW,
                is_responded=True,
                response_text="Thank you Carol! We're working on our delivery times.",
                location_id=location_id,
                data_source="fake_reputation",
                data_completeness=0.8,
            ),
        ])

    def fetch_brand_mentions(
        self, site_id: str
    ) -> Result[list[BrandMention], GrowthDataProviderError]:
        self.calls.append(("mentions", None))
        if self._fail:
            return Err(GrowthDataProviderError("fake reputation provider forced failure"))
        return Ok([
            BrandMention(
                mention_id="ment-001",
                platform="twitter",
                url="https://twitter.com/user/status/123",
                text="Just tried Acme Corp's service — impressed!",
                sentiment="positive",
                date=_NOW,
                data_source="fake_reputation",
            ),
        ])

    def name(self) -> str:
        return "fake_reputation"


class FakeAnalyticsDataProvider:
    """Default test double for analytics data."""

    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[tuple[str, str]] = []

    def fetch_snapshot(
        self,
        site_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Result[AnalyticsSnapshot, GrowthDataProviderError]:
        self.calls.append(("snapshot", site_id))
        if self._fail:
            return Err(GrowthDataProviderError("fake analytics provider forced failure"))
        return Ok(AnalyticsSnapshot(
            site_id=site_id,
            captured_at=end_date,
            sessions=1250,
            users=980,
            pageviews=4200,
            bounce_rate=0.42,
            avg_session_duration_s=185.0,
            conversions=38,
            conversion_rate=0.0304,
            clicks=890,
            impressions=12400,
            ctr=0.072,
            avg_position=14.3,
            data_source="fake_analytics",
            data_completeness=0.75,
        ))

    def fetch_top_pages(
        self,
        site_id: str,
        limit: int = 10,
    ) -> Result[list[TopPage], GrowthDataProviderError]:
        self.calls.append(("top_pages", site_id))
        if self._fail:
            return Err(GrowthDataProviderError("fake analytics provider forced failure"))
        return Ok([
            TopPage(
                url=f"https://{site_id}/",
                sessions=450,
                pageviews=780,
                bounce_rate=0.38,
                data_source="fake_analytics",
            ),
            TopPage(
                url=f"https://{site_id}/products",
                sessions=310,
                pageviews=620,
                bounce_rate=0.45,
                data_source="fake_analytics",
            ),
        ][:limit])

    def fetch_top_keywords(
        self,
        site_id: str,
        limit: int = 20,
    ) -> Result[list[TopKeyword], GrowthDataProviderError]:
        self.calls.append(("top_keywords", site_id))
        if self._fail:
            return Err(GrowthDataProviderError("fake analytics provider forced failure"))
        return Ok([
            TopKeyword(
                keyword="best product example",
                clicks=220,
                impressions=3200,
                ctr=0.069,
                avg_position=8.5,
                data_source="fake_analytics",
            ),
            TopKeyword(
                keyword="example service review",
                clicks=145,
                impressions=2100,
                ctr=0.069,
                avg_position=12.1,
                data_source="fake_analytics",
            ),
        ][:limit])

    def name(self) -> str:
        return "fake_analytics"


class FakeRankTrackingProvider:
    """Default test double for rank tracking data."""

    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[str] = []

    def fetch_rankings(
        self,
        site_id: str,
        keywords: list[str],
        device: str = "desktop",
        geo: str | None = None,
    ) -> Result[list[RankingSnapshot], GrowthDataProviderError]:
        self.calls.append(site_id)
        if self._fail:
            return Err(GrowthDataProviderError("fake rank tracking provider forced failure"))
        now = datetime.now(timezone.utc)
        snapshots = []
        for i, kw in enumerate(keywords):
            snapshots.append(RankingSnapshot(
                site_id=site_id,
                keyword=kw,
                position=float(5 + i * 3),  # deterministic positions for testing
                device=device,
                geo=geo,
                captured_at=now,
                previous_position=float(7 + i * 3),
                url=f"https://{site_id}/page-{i}",
                data_source="fake_rank_tracking",
                data_completeness=0.6,
            ))
        return Ok(snapshots)

    def name(self) -> str:
        return "fake_rank_tracking"


class FakeOutreachDataProvider:
    """Default test double for outreach/contact-discovery data."""

    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.calls: list[str] = []

    def fetch_contacts(
        self, domain: str
    ) -> Result[list[ContactRecord], GrowthDataProviderError]:
        self.calls.append(domain)
        if self._fail:
            return Err(GrowthDataProviderError("fake outreach provider forced failure"))
        return Ok([
            ContactRecord(
                domain=domain,
                email=f"editor@{domain}",
                first_name="Jane",
                last_name="Editor",
                title="Editor in Chief",
                confidence=0.82,
                data_source="fake_outreach",
            ),
        ])

    def fetch_domain_qualification(
        self, domain: str
    ) -> Result[DomainQualificationData, GrowthDataProviderError]:
        self.calls.append(domain)
        if self._fail:
            return Err(GrowthDataProviderError("fake outreach provider forced failure"))
        return Ok(DomainQualificationData(
            domain=domain,
            domain_authority=42.0,
            spam_score=0.05,
            monthly_traffic=15000.0,
            is_relevant=True,
            topics=["technology", "software", "productivity"],
            data_source="fake_outreach",
            data_completeness=0.65,
        ))

    def name(self) -> str:
        return "fake_outreach"
