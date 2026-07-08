"""Tests for GoalEngine."""
from agentic.goal.goal_engine import GoalEngine
from agentic.goal.models import GoalContext, Goal
from intelligence.ai.providers.fake_provider import FakeProvider

def test_goal_engine_parse_success():
    """Test successful objective parsing."""
    responses = {
        "goal_parsing": '{"target_metric": "organic_traffic", "magnitude": "25", "timeframe_days": 30, "target_site_id": "site_1", "target_page_set": []}'
    }
    provider = FakeProvider(responses=responses)
    engine = GoalEngine(provider)
    context = GoalContext(tenant_id="test_tenant")
    
    result = engine.parse("Increase organic traffic by 25%", context)
    
    assert result.is_ok
    goal = result.unwrap()
    assert isinstance(goal, Goal)
    assert goal.structured_objective.target_metric == "organic_traffic"
    assert goal.structured_objective.magnitude == "25"
    assert goal.structured_objective.timeframe_days == 30
    assert goal.structured_objective.target_site_id == "site_1"

def test_goal_engine_parse_failure():
    """Test handling of invalid JSON response."""
    responses = {
        "goal_parsing": '{"target_metric": "broken json'
    }
    provider = FakeProvider(responses=responses)
    engine = GoalEngine(provider)
    context = GoalContext(tenant_id="test_tenant")
    
    result = engine.parse("Increase traffic", context)
    assert result.is_err
    assert "Failed to parse" in result.error
