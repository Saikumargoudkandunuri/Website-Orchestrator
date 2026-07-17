"""Image SEO Engine — detects real image-markup deficiencies from live page
HTML: missing ALT, poor filenames, missing captions, missing lazy loading,
missing dimensions. Operates on real HTML fetched from the Publishing_Adapter
(never a fixture). Missing-ALT is surfaced as a finding only — its executable
fix already exists via the Fix_Generator/Governance ``update_alt_text`` path,
so this engine never duplicates that write path.
"""
from __future__ import annotations

from engines.image_seo.models import ImageFinding, ImageProposal, ImageSeoReport
from engines.image_seo.service import ImageSeoService

__all__ = ["ImageSeoService", "ImageFinding", "ImageProposal", "ImageSeoReport"]
