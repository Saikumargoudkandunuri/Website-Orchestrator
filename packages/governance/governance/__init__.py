"""Governance_Layer subsystem — approval, rollback, and audit workflow.

The only path through which a SuggestedFix status transition occurs. Interacts
with the Digital_Twin and Publishing_Adapter exclusively through the Protocols
published in Core_Package. Depends only on Core_Package.
"""

from governance.service import GovernanceService

__all__: list[str] = ["GovernanceService"]
