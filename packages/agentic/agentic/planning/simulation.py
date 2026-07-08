"""Simulation Engine for the planning layer (M6 Build Phase B)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from agentic.planning.models import Plan


class SimulatedTimeline(BaseModel):
    """Timeline simulation results."""
    total_duration_hours: float
    critical_path_steps: int
    concurrency_savings_hours: float


class SimulationOutcome(BaseModel):
    """The simulated outcome of running a Plan."""
    simulated_traffic_gain: float
    simulated_ranking_gain: float
    simulated_content_pages_created: int
    total_estimated_cost_dollars: float
    total_estimated_tokens: int
    timeline: SimulatedTimeline
    confidence_interval: tuple[float, float]


class SimulationEngine:
    """Simulates plan outcomes using deterministic heuristics."""
    
    def simulate_outcomes(self, plan: Plan) -> SimulationOutcome:
        """Deterministically simulate the outcomes of executing the plan."""
        nodes = list(plan.graph.nodes.values())
        
        # 1. Resource usage sums
        total_cost = sum(n.estimated_cost for n in nodes)
        total_tokens = sum(n.estimated_tokens for n in nodes)
        
        # 2. Heuristics for SEO and Traffic gains
        # Base traffic gain: each content generation action gives +10 units of traffic,
        # audits give +5, fixes give +15, publishing gives +20.
        traffic_gain = 0.0
        ranking_gain = 0.0
        pages_created = 0
        
        for n in nodes:
            action = (n.action_type or "").lower()
            if "content" in action:
                traffic_gain += 10.0
                ranking_gain += 0.2
                pages_created += 1
            elif "audit" in action:
                traffic_gain += 5.0
                ranking_gain += 0.1
            elif "fix" in action:
                traffic_gain += 15.0
                ranking_gain += 0.3
            elif "publish" in action:
                traffic_gain += 20.0
                ranking_gain += 0.4
                
        # 3. Timeline critical path & concurrency simulation
        # Simplistic critical path: sum of serial durations of dependent chains.
        # Nodes with no dependencies can run in parallel.
        total_duration = sum(n.estimated_duration for n in nodes)
        
        # If nodes have dependencies, the critical path is the maximum path depth.
        # Let's compute a simple estimation of concurrency savings.
        non_dependent_nodes = sum(1 for n in nodes if not n.dependencies)
        concurrency_savings = 0.0
        if len(nodes) > 1 and non_dependent_nodes > 1:
            # We assume independent nodes can run concurrently, saving some fraction of time
            independent_durations = [n.estimated_duration for n in nodes if not n.dependencies]
            concurrency_savings = sum(independent_durations) - max(independent_durations or [0.0])

        total_duration_hours = max(0.0, total_duration - concurrency_savings)

        # 4. Confidence Interval
        # Based on average node success probability
        if nodes:
            avg_success = sum(n.success_probability for n in nodes) / len(nodes)
        else:
            avg_success = 1.0
            
        lower_bound = traffic_gain * (avg_success * 0.8)
        upper_bound = traffic_gain * (avg_success * 1.2)

        return SimulationOutcome(
            simulated_traffic_gain=traffic_gain,
            simulated_ranking_gain=ranking_gain,
            simulated_content_pages_created=pages_created,
            total_estimated_cost_dollars=total_cost,
            total_estimated_tokens=total_tokens,
            timeline=SimulatedTimeline(
                total_duration_hours=total_duration_hours,
                critical_path_steps=len(nodes),
                concurrency_savings_hours=concurrency_savings,
            ),
            confidence_interval=(lower_bound, upper_bound),
        )
