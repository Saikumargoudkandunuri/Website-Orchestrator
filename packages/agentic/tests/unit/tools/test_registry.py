"""Tests for Tool Registry and Selector."""
from agentic.goal.models import Goal, GoalContext, GoalConstraints, RiskLevel
from agentic.tools.registry import InMemoryToolRegistry, ToolMetadata, Capability
from agentic.tools.selector import ToolSelector, ExecutionPolicy

def test_registry_and_selector():
    """Test registry indexing and policy-based selection."""
    registry = InMemoryToolRegistry()
    
    # Register a few tools
    audit_tool = ToolMetadata(
        name="seo_audit",
        capability=Capability(domain="seo", action="audit"),
        input_schema={},
        output_schema={},
        cost_estimate=2.50,
        requires_approval=False,
        risk_level=RiskLevel.LOW,
        owning_package="engines"
    )
    publish_tool = ToolMetadata(
        name="wp_publish",
        capability=Capability(domain="content", action="publish"),
        input_schema={},
        output_schema={},
        cost_estimate=0.50,
        requires_approval=True,
        risk_level=RiskLevel.HIGH,
        owning_package="publishing_adapter"
    )
    registry.register(audit_tool)
    registry.register(publish_tool)
    
    assert registry.get_by_name("seo_audit") == audit_tool
    assert len(registry.find_by_capability(Capability(domain="content", action="publish"))) == 1
    
    selector = ToolSelector(registry)
    goal = Goal(
        raw_objective="Do an audit",
        context=GoalContext(tenant_id="tenant_1"),
        constraints=GoalConstraints(max_budget_dollars=1.0)
    )
    
    # Goal max budget is 1.0, audit_tool costs 2.50. It should be filtered out.
    candidates = selector.select(goal, required_capability=Capability(domain="seo", action="audit"))
    assert len(candidates) == 0
    
    # Relax budget
    goal.constraints.max_budget_dollars = 5.0
    candidates = selector.select(goal, required_capability=Capability(domain="seo", action="audit"))
    assert len(candidates) == 1
    assert candidates[0].name == "seo_audit"
