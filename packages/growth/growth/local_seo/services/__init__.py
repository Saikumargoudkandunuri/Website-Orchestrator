"""Local SEO services."""
from __future__ import annotations
from datetime import datetime, timezone
from core.results import Ok, Result
from growth.local_seo.models import (
    LocalSeoReport,
    LocalSeoProfile,
    NapConsistencyResult,
    NapInconsistency,
)
from growth.shared.provider_abstraction.local_seo_data_provider_interface import LocalSeoDataProvider
from growth.errors import GrowthAnalysisError

__all__ = ["LocalSeoService"]


class LocalSeoService:
    """
    Local SEO business logic (§4.3).
    
    REAL: NAP consistency checking (cross-site structured contact data).
    Provider-fake: GBP optimization, citation management.
    """

    def __init__(self, provider: LocalSeoDataProvider):
        self._provider = provider

    def analyze(
        self,
        site_id: str,
        pages_with_contact_data: list[dict],  # From M2 EeatSection, SchemaIntelligenceSection
    ) -> Result[LocalSeoReport, GrowthAnalysisError]:
        """
        Analyze site for local SEO opportunities.
        
        Cross-references M2's EeatSection.contact_info_present and LocalBusiness schema blocks.
        """
        # Extract NAP data from each page's structured data
        nap_data = self._extract_nap_data(pages_with_contact_data)
        
        # REAL: NAP consistency checking
        nap_consistency = self._check_nap_consistency(nap_data)
        
        # Provider-fake: Fetch GBP/citation data
        locations = self._build_location_profiles(site_id, nap_data)
        
        # Composite local SEO score
        local_seo_score = self._compute_local_seo_score(locations, nap_consistency)
        
        report = LocalSeoReport(
            site_id=site_id,
            locations=locations,
            nap_consistency=nap_consistency,
            local_seo_score=local_seo_score,
            computed_at=datetime.now(timezone.utc),
            version=1,
        )
        return Ok(report)

    def _extract_nap_data(self, pages: list[dict]) -> list[dict]:
        """
        Extract NAP (Name/Address/Phone) from M2 structured data.
        
        Sources:
        - EeatSection.contact_info_present
        - SchemaIntelligenceSection LocalBusiness blocks
        """
        nap_records = []
        for page in pages:
            page_id = page.get("page_id", "")
            
            # Extract from schema blocks (LocalBusiness type)
            schema_blocks = page.get("schema_blocks", [])
            for block in schema_blocks:
                if block.get("type") == "LocalBusiness":
                    nap_records.append({
                        "page_id": page_id,
                        "name": block.get("name", ""),
                        "address": self._format_address(block.get("address", {})),
                        "phone": block.get("telephone", ""),
                        "source": "schema",
                    })
            
            # Extract from contact info presence (if available)
            contact_info = page.get("contact_info", {})
            if contact_info:
                nap_records.append({
                    "page_id": page_id,
                    "name": contact_info.get("business_name", ""),
                    "address": contact_info.get("address", ""),
                    "phone": contact_info.get("phone", ""),
                    "source": "content",
                })
        
        return nap_records

    def _format_address(self, addr: dict) -> str:
        """Format structured address into comparable string."""
        parts = [
            addr.get("streetAddress", ""),
            addr.get("addressLocality", ""),
            addr.get("addressRegion", ""),
            addr.get("postalCode", ""),
        ]
        return ", ".join(p for p in parts if p).strip()

    def _check_nap_consistency(self, nap_data: list[dict]) -> NapConsistencyResult:
        """
        REAL capability: Check NAP consistency across all pages.
        
        Flags inconsistencies where same location has different NAP values.
        This is computable today without provider data.
        """
        inconsistencies: list[NapInconsistency] = []
        pages_checked = [rec["page_id"] for rec in nap_data]
        
        # Compare all pairs
        for i, rec1 in enumerate(nap_data):
            for rec2 in nap_data[i + 1:]:
                # Check name inconsistency
                if rec1["name"] and rec2["name"] and rec1["name"] != rec2["name"]:
                    if self._are_likely_same_business(rec1, rec2):
                        inconsistencies.append(NapInconsistency(
                            page_id_1=rec1["page_id"],
                            page_id_2=rec2["page_id"],
                            field="name",
                            value_1=rec1["name"],
                            value_2=rec2["name"],
                            severity="critical",
                        ))
                
                # Check phone inconsistency
                if rec1["phone"] and rec2["phone"] and rec1["phone"] != rec2["phone"]:
                    if self._are_likely_same_business(rec1, rec2):
                        inconsistencies.append(NapInconsistency(
                            page_id_1=rec1["page_id"],
                            page_id_2=rec2["page_id"],
                            field="phone",
                            value_1=rec1["phone"],
                            value_2=rec2["phone"],
                            severity="critical",
                        ))
                
                # Check address inconsistency
                if rec1["address"] and rec2["address"]:
                    if not self._addresses_match(rec1["address"], rec2["address"]):
                        if self._are_likely_same_business(rec1, rec2):
                            inconsistencies.append(NapInconsistency(
                                page_id_1=rec1["page_id"],
                                page_id_2=rec2["page_id"],
                                field="address",
                                value_1=rec1["address"],
                                value_2=rec2["address"],
                                severity="warning",  # Address formatting variations are common
                            ))
        
        is_consistent = len(inconsistencies) == 0
        confidence = 1.0 if len(nap_data) > 0 else 0.0
        
        return NapConsistencyResult(
            is_consistent=is_consistent,
            inconsistencies=inconsistencies,
            pages_checked=pages_checked,
            confidence_score=confidence,
        )

    def _are_likely_same_business(self, rec1: dict, rec2: dict) -> bool:
        """Heuristic: are these two records likely the same business?"""
        # Simple heuristic: if either name or phone matches, likely same business
        name_match = rec1["name"] and rec2["name"] and rec1["name"] == rec2["name"]
        phone_match = rec1["phone"] and rec2["phone"] and rec1["phone"] == rec2["phone"]
        return name_match or phone_match

    def _addresses_match(self, addr1: str, addr2: str) -> bool:
        """Fuzzy address comparison (normalize then compare)."""
        def normalize(addr: str) -> str:
            # Remove common variations
            return (addr.lower()
                    .replace("street", "st")
                    .replace("avenue", "ave")
                    .replace("road", "rd")
                    .replace("suite", "ste")
                    .replace(",", "")
                    .replace(".", "")
                    .strip())
        
        return normalize(addr1) == normalize(addr2)

    def _build_location_profiles(self, site_id: str, nap_data: list[dict]) -> list[LocalSeoProfile]:
        """
        Build location profiles with GBP/citation data (provider-fake).
        
        In reality, would fetch from Yext/BrightLocal equivalent.
        """
        profiles: list[LocalSeoProfile] = []
        
        # Group NAP records by unique location (deduplicate)
        unique_locations: dict[str, dict] = {}
        for rec in nap_data:
            key = f"{rec['name']}|{rec['phone']}"
            if key not in unique_locations:
                unique_locations[key] = rec
        
        # For each unique location, build profile with provider-fake GBP/citation data
        for i, (key, rec) in enumerate(unique_locations.items()):
            # Provider-fake: would call self._provider.get_gbp_profile() here
            profiles.append(LocalSeoProfile(
                location_id=f"loc-{site_id}-{i}",
                page_id=rec["page_id"],
                name=rec["name"],
                address=rec["address"],
                phone=rec["phone"],
                # Provider-fake data below
                gbp_categories=["Service", "Professional Services"],
                gbp_attributes=["wheelchair_accessible", "accepts_credit_cards"],
                gbp_hours_complete=True,
                gbp_photo_count=15,
                gbp_post_cadence_score=0.8,
                citation_count=45,
                citation_consistency_score=0.92,
                has_local_business_schema=True,
                schema_validation_errors=[],
            ))
        
        return profiles

    def _compute_local_seo_score(
        self, locations: list[LocalSeoProfile], nap_consistency: NapConsistencyResult
    ) -> dict:
        """
        Compute composite local SEO score.
        
        Transparent breakdown following M3's SeoScoreBreakdown pattern.
        """
        # NAP consistency weight (critical)
        nap_score = 1.0 if nap_consistency.is_consistent else 0.5
        
        # GBP optimization (average across locations)
        gbp_scores = [
            (loc.gbp_hours_complete * 0.2 +
             min(loc.gbp_photo_count / 20, 1.0) * 0.3 +
             loc.gbp_post_cadence_score * 0.3 +
             (len(loc.gbp_categories) > 0) * 0.2)
            for loc in locations
        ]
        gbp_score = sum(gbp_scores) / len(gbp_scores) if gbp_scores else 0.0
        
        # Citation consistency (average across locations)
        citation_scores = [loc.citation_consistency_score for loc in locations]
        citation_score = sum(citation_scores) / len(citation_scores) if citation_scores else 0.0
        
        # Schema validation (all locations have valid schema?)
        schema_score = 1.0 if all(loc.has_local_business_schema for loc in locations) else 0.5
        
        # Overall score
        overall = (
            nap_score * 0.4 +
            gbp_score * 0.3 +
            citation_score * 0.2 +
            schema_score * 0.1
        )
        
        return {
            "overall": round(overall, 2),
            "breakdown": {
                "nap_consistency": round(nap_score, 2),
                "gbp_optimization": round(gbp_score, 2),
                "citation_quality": round(citation_score, 2),
                "schema_validity": round(schema_score, 2),
            },
            "weights": {
                "nap_consistency": 0.4,
                "gbp_optimization": 0.3,
                "citation_quality": 0.2,
                "schema_validity": 0.1,
            },
        }
