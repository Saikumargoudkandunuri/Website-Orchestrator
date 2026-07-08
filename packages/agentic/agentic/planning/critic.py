"""Critic service for the planning layer (M6 Build Phase B)."""
from __future__ import annotations

from agentic.planning.models import Plan


class Critic:
    """Interrogates plans to identify structural inefficiencies or governance conflicts."""
    
    def critique_plan(self, plan: Plan) -> list[str]:
        """Analyze a plan and return a list of critiques/invalidation warnings."""
        critiques: list[str] = []
        nodes = list(plan.graph.nodes.values())
        
        if not nodes:
            critiques.append("Plan is empty and has no actions.")
            return critiques
            
        # 1. Cost critique: Is there a cheaper approach?
        total_cost = sum(n.estimated_cost for n in nodes)
        if total_cost > 10.0:  # arbitrary threshold for optimization
            critiques.append(
                f"Plan estimated cost (${total_cost:.2f}) exceeds $10.00 threshold. "
                "Evaluate if cheaper LLM templates or cached audits can be utilized."
            )
            
        # 2. Size/Complexity critique: Can fewer actions achieve the same result?
        if len(nodes) > 8:
            critiques.append(
                f"Plan contains {len(nodes)} steps. High complexity increases failure risk. "
                "Consider consolidating content creation and linking actions."
            )
            
        # 3. Governance critique: Will publishing create governance issues?
        publish_nodes = [n for n in nodes if "publish" in (n.action_type or "").lower()]
        for p in publish_nodes:
            if not p.approval_required:
                critiques.append(
                    f"Publish step '{p.id}' does not require approval. "
                    "All publishing operations must pass through approval queues per governance policy."
                )
                
        # 4. Redundancy/Duplication: Check for duplicate actions in the plan
        seen_actions = set()
        for n in nodes:
            action_key = (n.action_type, n.tool_name)
            if action_key in seen_actions:
                critiques.append(
                    f"Duplicate action step detected: {n.action_type} via {n.tool_name}. "
                    "This may represent redundant work."
                )
            seen_actions.add(action_key)
            
        # 5. Technical SEO vs Content Generation:
        # Could technical SEO fixes solve this without generating new content?
        has_technical = any("technical" in (n.action_type or "").lower() or "fix" in (n.action_type or "").lower() for n in nodes)
        has_content = any("content" in (n.action_type or "").lower() for n in nodes)
        if has_content and not has_technical:
            critiques.append(
                "Plan includes content generation but lacks technical SEO validation. "
                "Ensure indexing errors or page speeds are not the root bottleneck first."
            )

        return critiques
