"""Reasoner service for the planning layer (M6 Build Phase B)."""
from __future__ import annotations

from brain.decision.engine import DecisionEngine
from agentic.goal.models import RiskLevel
from agentic.planning.models import Plan


class Reasoner:
    """Evaluates plans across 11 distinct, explainable dimensions."""
    
    def __init__(self, decision_engine: DecisionEngine | None = None) -> None:
        self._decision_engine = decision_engine
        
    def score_plan(self, plan: Plan) -> dict[str, float]:
        """Score the plan against 11 dimensions."""
        nodes = list(plan.graph.nodes.values())
        if not nodes:
            return {
                "business_impact": 0.0,
                "seo_impact": 0.0,
                "growth_impact": 0.0,
                "cost": 1.0,  # Best score for 0 cost
                "complexity": 1.0,  # Best score for 0 complexity
                "execution_time": 1.0,
                "historical_success": 0.5,
                "risk": 1.0,  # Best score for 0 risk
                "dependencies": 1.0,
                "resource_usage": 1.0,
                "approval_overhead": 1.0,
            }
            
        # 1. Business Impact: average of node business_value
        business_impact = sum(n.business_value for n in nodes) / len(nodes)
        
        # 2. SEO Impact: count of SEO nodes normalized
        seo_nodes = sum(1 for n in nodes if "seo" in (n.action_type or "").lower())
        seo_impact = min(1.0, seo_nodes * 0.25)
        
        # 3. Growth Impact: count of growth-generating content actions
        growth_nodes = sum(1 for n in nodes if "content" in (n.action_type or "").lower())
        growth_impact = min(1.0, growth_nodes * 0.20)
        
        # 4. Cost score: inverse of total cost
        total_cost = sum(n.estimated_cost for n in nodes)
        cost_score = max(0.0, 1.0 - (total_cost / 50.0))
        
        # 5. Complexity: lower is better (inversed ratio of nodes)
        complexity_score = max(0.0, 1.0 - (len(nodes) / 20.0))
        
        # 6. Execution Time: lower is better (inversed total duration)
        total_duration = sum(n.estimated_duration for n in nodes)
        time_score = max(0.0, 1.0 - (total_duration / 24.0))
        
        # 7. Historical Success: average success probability of nodes
        historical_success = sum(n.success_probability for n in nodes) / len(nodes)
        
        # 8. Risk score: inverse of critical/high risk steps
        high_risk_count = sum(1 for n in nodes if n.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL))
        risk_score = max(0.0, 1.0 - (high_risk_count / len(nodes)))
        
        # 9. Dependencies: fewer is better
        deps_count = sum(len(n.dependencies) for n in nodes)
        deps_score = max(0.0, 1.0 - (deps_count / len(nodes)))
        
        # 10. Resource Usage: tokens and cost footprint (lower is better)
        total_tokens = sum(n.estimated_tokens for n in nodes)
        resource_score = max(0.0, 1.0 - (total_tokens / 10000.0) - (total_cost / 100.0))
        
        # 11. Approval Overhead: ratio of steps needing approval (lower is better)
        approval_count = sum(1 for n in nodes if n.approval_required)
        approval_score = max(0.0, 1.0 - (approval_count / len(nodes)))
        
        return {
            "business_impact": business_impact,
            "seo_impact": seo_impact,
            "growth_impact": growth_impact,
            "cost": cost_score,
            "complexity": complexity_score,
            "execution_time": time_score,
            "historical_success": historical_success,
            "risk": risk_score,
            "dependencies": deps_score,
            "resource_usage": resource_score,
            "approval_overhead": approval_score,
        }
