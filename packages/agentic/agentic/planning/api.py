"""API router for the planning layer (M6 Build Phase B)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from agentic.planning.wiring import PlanningContainer
from agentic.goal.repositories import GoalRepository
from agentic.tools.selector import ExecutionPolicy


def build_planning_router() -> APIRouter:
    """Build the agentic planning API router."""
    router = APIRouter(prefix="/agentic", tags=["agentic-planning"])
    
    def _planning(request: Request) -> PlanningContainer:
        container = getattr(request.app.state, "agentic_planning", None)
        if container is None:
            raise HTTPException(503, "Agentic planning container is not available.")
        return container
        
    def _goals(request: Request) -> GoalRepository:
        goal_repo = getattr(request.app.state, "goal_repository", None)
        if goal_repo is None:
            raise HTTPException(503, "Goal repository is not available.")
        return goal_repo

    @router.post("/goals/{goal_id}/plan")
    def create_goal_plan(goal_id: str, request: Request) -> dict[str, Any]:
        """Generate and save a Plan for a specific goal."""
        container = _planning(request)
        goal_repo = _goals(request)
        
        goal = goal_repo.get(container.tenant_id, goal_id)
        if not goal:
            raise HTTPException(404, f"Goal {goal_id} not found.")
            
        policy = ExecutionPolicy(tenant_id=container.tenant_id)
        plan = container.planner.plan(goal, policy)
        
        # Save the plan and graph
        container.plan_repo.save(plan)
        container.graph_repo.save(
            plan.id,
            plan.graph,
            tenant_id=container.tenant_id,
            site_id=plan.site_id,
        )
        
        return plan.model_dump(mode="json")

    @router.get("/plans/{plan_id}")
    def get_plan(plan_id: str, request: Request) -> dict[str, Any]:
        """Retrieve a Plan by ID."""
        container = _planning(request)
        plan = container.plan_repo.get(container.tenant_id, plan_id)
        if not plan:
            raise HTTPException(404, f"Plan {plan_id} not found.")
        return plan.model_dump(mode="json")

    @router.get("/plans/{plan_id}/graph")
    def get_plan_graph(plan_id: str, request: Request) -> dict[str, Any]:
        """Retrieve the ExecutionGraph for a Plan."""
        container = _planning(request)
        graph = container.graph_repo.get_for_plan(container.tenant_id, plan_id)
        if not graph:
            raise HTTPException(404, f"Execution graph not found for plan {plan_id}.")
        return graph.model_dump(mode="json")

    @router.post("/plans/{plan_id}/simulate")
    def simulate_plan(plan_id: str, request: Request) -> dict[str, Any]:
        """Run simulation on the plan and save outcome."""
        container = _planning(request)
        plan = container.plan_repo.get(container.tenant_id, plan_id)
        if not plan:
            raise HTTPException(404, f"Plan {plan_id} not found.")
            
        outcome = container.simulation_engine.simulate_outcomes(plan)
        container.sim_repo.save(
            plan_id,
            outcome,
            tenant_id=container.tenant_id,
            site_id=plan.site_id,
        )
        
        return outcome.model_dump(mode="json")

    @router.get("/plans/{plan_id}/alternatives")
    def get_plan_alternatives(plan_id: str, request: Request) -> list[dict[str, Any]]:
        """Retrieve alternatives for a Plan."""
        container = _planning(request)
        plan = container.plan_repo.get(container.tenant_id, plan_id)
        if not plan:
            raise HTTPException(404, f"Plan {plan_id} not found.")
        return [alt.model_dump(mode="json") for alt in plan.alternatives]

    return router
