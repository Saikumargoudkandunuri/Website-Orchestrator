"""Risk Analyzer service for the planning layer (M6 Build Phase B)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from agentic.goal.models import RiskLevel
from agentic.planning.models import Plan


class RiskFactor(BaseModel):
    """A single risk assessment factor with explanation and score."""
    score: float  # 0.0 (no risk) to 1.0 (extremely high risk)
    reasoning: str


class RiskAnalysis(BaseModel):
    """Composite risk assessment of a plan."""
    execution_risk: RiskFactor
    seo_risk: RiskFactor
    business_risk: RiskFactor
    rollback_difficulty: RiskFactor
    provider_dependency: RiskFactor
    approval_requirement: RiskFactor
    composite_risk_score: float
    overall_confidence: float


class RiskAnalyzer:
    """Estimates execution, SEO, and business risks with explainable paths."""
    
    def analyze_risk(self, plan: Plan) -> RiskAnalysis:
        """Analyze the plan's components and generate a detailed RiskAnalysis."""
        nodes = list(plan.graph.nodes.values())
        if not nodes:
            # Empty plan risk
            empty_factor = RiskFactor(score=0.0, reasoning="No nodes in plan.")
            return RiskAnalysis(
                execution_risk=empty_factor,
                seo_risk=empty_factor,
                business_risk=empty_factor,
                rollback_difficulty=empty_factor,
                provider_dependency=empty_factor,
                approval_requirement=empty_factor,
                composite_risk_score=0.0,
                overall_confidence=1.0,
            )

        # 1. Execution Risk: proportional to node risk_levels
        high_risk_count = sum(1 for n in nodes if n.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL))
        exec_score = min(1.0, high_risk_count / len(nodes))
        exec_reason = f"Plan contains {high_risk_count} high/critical risk steps out of {len(nodes)} total steps."
        
        # 2. SEO Risk: risk of modifying critical pages or search parameters
        seo_count = sum(1 for n in nodes if "seo" in (n.action_type or "").lower() or "audit" in (n.action_type or "").lower())
        seo_score = min(1.0, seo_count * 0.15)
        seo_reason = f"Identified {seo_count} SEO-related operations which could impact organic index status."
        
        # 3. Business Risk: likelihood of affecting conversion paths/revenues
        bus_score = min(1.0, sum(n.business_value for n in nodes) / len(nodes))
        bus_reason = f"Average business value stake is {bus_score:.2f} across plan nodes."
        
        # 4. Rollback Difficulty: proportional to non-empty rollback strategies
        missing_rollback = sum(1 for n in nodes if not n.rollback_strategy)
        rollback_score = min(1.0, missing_rollback / len(nodes))
        rollback_reason = f"Missing explicit rollback strategies for {missing_rollback} out of {len(nodes)} steps."
        
        # 5. Provider Dependency: ratio of steps calling third-party or LLM tooling
        llm_count = sum(1 for n in nodes if n.estimated_tokens > 0)
        provider_score = min(1.0, llm_count / len(nodes))
        provider_reason = f"Plan relies heavily on LLM provider processing: {llm_count} steps use token quotas."
        
        # 6. Approval Requirement: ratio of nodes requiring approval
        approval_count = sum(1 for n in nodes if n.approval_required)
        approval_score = min(1.0, approval_count / len(nodes))
        approval_reason = f"Found {approval_count} steps requiring human approval before execution."
        
        # Composite score
        composite = (exec_score + seo_score + bus_score + rollback_score + provider_score + approval_score) / 6.0
        
        # Confidence: negatively correlated with risk and missing rollback
        confidence = max(0.0, 1.0 - (composite * 0.5) - (rollback_score * 0.2))

        return RiskAnalysis(
            execution_risk=RiskFactor(score=exec_score, reasoning=exec_reason),
            seo_risk=RiskFactor(score=seo_score, reasoning=seo_reason),
            business_risk=RiskFactor(score=bus_score, reasoning=bus_reason),
            rollback_difficulty=RiskFactor(score=rollback_score, reasoning=rollback_reason),
            provider_dependency=RiskFactor(score=provider_score, reasoning=provider_reason),
            approval_requirement=RiskFactor(score=approval_score, reasoning=approval_reason),
            composite_risk_score=composite,
            overall_confidence=confidence,
        )
