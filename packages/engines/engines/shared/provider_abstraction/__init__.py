"""Provider abstraction for third-party SEO data (Competitor, Backlink engines)."""

from engines.shared.provider_abstraction.fake_seo_data_provider import (
    AlternativeFakeBacklinkDataProvider,
    AlternativeFakeCompetitorDataProvider,
    FakeBacklinkDataProvider,
    FakeCompetitorDataProvider,
)
from engines.shared.provider_abstraction.seo_data_provider_interface import (
    BacklinkDataProvider,
    BacklinkRecord,
    CompetitorBacklink,
    CompetitorDataProvider,
    CompetitorKeyword,
    CompetitorPage,
    ReferringDomain,
)

__all__ = [
    "CompetitorDataProvider",
    "BacklinkDataProvider",
    "CompetitorPage",
    "CompetitorKeyword",
    "CompetitorBacklink",
    "BacklinkRecord",
    "ReferringDomain",
    "FakeCompetitorDataProvider",
    "FakeBacklinkDataProvider",
    "AlternativeFakeCompetitorDataProvider",
    "AlternativeFakeBacklinkDataProvider",
]
