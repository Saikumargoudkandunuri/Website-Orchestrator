"""Governance Gate for verifying execution safety (M6 Build Phase D)."""
from __future__ import annotations

from typing import Any

from agentic.goal.models import RiskLevel
from agentic.planning.models import ExecutionNode
from agentic.tools.selector import ExecutionPolicy
from growth.auth import GrowthIdentity


class GovernanceGate:
    """Verifies permission, approval, tenant isolation, and risk limits before executing actions."""
    
    def check_governance(
        self,
        node: ExecutionNode,
        identity: GrowthIdentity,
        policy: ExecutionPolicy,
        tenant_id: str,
    ) -> tuple[bool, str]:
        """
        Verify execution permissions and safety parameters.
        Returns (success, reason).
        """
        # 1. Tenant Isolation Check
        # Ensure target node's tenant/goal corresponds to the active tenant
        if identity.tenant_id != tenant_id:
            return False, f"Tenant isolation violation: requested '{tenant_id}', identity is '{identity.tenant_id}'."

        # 2. Permission Check
        # Editor or admin/owner permission required for write actions
        is_write = "publish" in (node.action_type or "").lower() or "fix" in (node.action_type or "").lower()
        if is_write:
            # Requires write / publish permissions
            required_perms = {"write", "publish"}
            identity_perms = set(identity.permissions)
            if not identity_perms.intersection(required_perms):
                return False, f"Permission violation: write/publish permission required for node '{node.id}'."

        # 3. Approval Check
        # Nodes requiring approval must be flagged, queued for human review
        if node.approval_required:
            # In a real engine, this routes to Approval Queue. In our Gate, we block and verify
            # if approved. If no approval metadata is provided, we fail the gate.
            approved = node.required_inputs.get("approved_by_human", False)
            if not approved:
                return False, f"Approval violation: Action requires human approval before execution."

        # 4. Risk Level Check
        # Node risk must not exceed permitted policy risk level
        risk_hierarchy = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }
        node_risk_val = risk_hierarchy.get(node.risk_level, 0)
        allowed_risk_val = risk_hierarchy.get(policy.allowed_risk_level, RiskLevel.MEDIUM)
        
        if node_risk_val > allowed_risk_val:
            return False, f"Risk limit exceeded: node risk '{node.risk_level}' exceeds allowed policy risk '{policy.allowed_risk_level}'."
            
        return True, "Passed governance checks."
