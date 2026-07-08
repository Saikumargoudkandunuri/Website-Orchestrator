"""Execution Graph DAG utilities and validation."""
from __future__ import annotations

from agentic.planning.models import ExecutionEdge, ExecutionGraph, ExecutionNode


class DependencyError(ValueError):
    """Raised when there is a dependency validation error (e.g., cyclic dependency)."""


def validate_dag(graph: ExecutionGraph) -> None:
    """Validate that the ExecutionGraph is a valid Directed Acyclic Graph (DAG)."""
    # 1. Check that all edges refer to existing nodes
    node_ids = set(graph.nodes.keys())
    for edge in graph.edges:
        if edge.from_node not in node_ids:
            raise DependencyError(f"Edge from non-existent node: {edge.from_node}")
        if edge.to_node not in node_ids:
            raise DependencyError(f"Edge to non-existent node: {edge.to_node}")

    # 2. Check for cycles using DFS
    visited = {}  # state: 0 = unvisited, 1 = visiting, 2 = visited
    
    # Build adjacency list
    adj = {node_id: [] for node_id in node_ids}
    for edge in graph.edges:
        adj[edge.from_node].append(edge.to_node)
        
    def dfs(u: str) -> None:
        visited[u] = 1
        for v in adj[u]:
            if visited.get(v, 0) == 1:
                raise DependencyError(f"Cyclic dependency detected: cycle contains {u} -> {v}")
            if visited.get(v, 0) == 0:
                dfs(v)
        visited[u] = 2

    for node_id in node_ids:
        if visited.get(node_id, 0) == 0:
            dfs(node_id)


def get_topological_sort(graph: ExecutionGraph) -> list[str]:
    """Return node IDs in topologically sorted order (dependencies first)."""
    validate_dag(graph)
    
    node_ids = set(graph.nodes.keys())
    adj = {node_id: [] for node_id in node_ids}
    in_degree = {node_id: 0 for node_id in node_ids}
    
    for edge in graph.edges:
        adj[edge.from_node].append(edge.to_node)
        in_degree[edge.to_node] += 1
        
    # Standard Kahn's algorithm
    queue = [u for u, deg in in_degree.items() if deg == 0]
    order = []
    
    while queue:
        u = queue.pop(0)
        order.append(u)
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
                
    if len(order) != len(node_ids):
        raise DependencyError("Failed topological sort (unexpected cycle/isolation)")
        
    return order
