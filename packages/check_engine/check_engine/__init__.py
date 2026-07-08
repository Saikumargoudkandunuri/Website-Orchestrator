"""Check_Engine subsystem — deterministic, rule-based issue detection.

Runs one function per check plus an aggregator, emitting structured
IssueCandidate objects. Never invokes an LLM. Depends only on Core_Package.
"""

from check_engine.checks import CheckEngine

__all__: list[str] = ["CheckEngine"]
