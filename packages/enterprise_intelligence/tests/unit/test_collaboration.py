"""Phase 5 — Enterprise Collaboration unit tests.

Tests cover: domain Intelligences profiles, ConsensusEngine voting, ArbitrationEngine
conflict resolution, LoadBalancer task routing, and shared substrate / safety checks.
"""

from __future__ import annotations

import pytest

from enterprise_intelligence.collaboration.intelligences.domain_intelligences import (
    SeoIntelligence,
    ContentIntelligence,
    TechnicalIntelligence,
    BusinessIntelligence,
)
from enterprise_intelligence.collaboration.engine import ArbitrationEngine, ConsensusEngine, LoadBalancer


class TestDomainIntelligences:
    def test_intelligence_creation(self):
        seo = SeoIntelligence()
        assert seo.name == "seo_intelligence"
        assert "seo" in seo.capabilities
        assert "seo_audit" in seo.tools

        content = ContentIntelligence()
        assert content.name == "content_intelligence"
        assert "content_generation" in content.capabilities


class TestArbitrationEngine:
    def test_arbitrate_by_priority(self):
        arb = ArbitrationEngine()
        
        low_pri = {
            "agent": "seo_intelligence",
            "action": "seo_audit",
            "risk_level": "low",
            "confidence": 0.8,
            "cost": 1.0,
        }
        high_pri = {
            "agent": "content_intelligence",
            "action": "content_generator",
            "risk_level": "high",
            "confidence": 0.8,
            "cost": 2.0,
        }
        
        winner, reason = arb.arbitrate([low_pri, high_pri], contested_resource="page-1")
        assert winner["agent"] == "content_intelligence"
        assert "priority" in reason

    def test_arbitrate_by_confidence(self):
        arb = ArbitrationEngine()
        
        low_conf = {
            "agent": "seo_intelligence",
            "action": "seo_audit",
            "risk_level": "normal",
            "confidence": 0.7,
            "cost": 1.0,
        }
        high_conf = {
            "agent": "technical_intelligence",
            "action": "speed_optimization",
            "risk_level": "normal",
            "confidence": 0.9,
            "cost": 1.0,
        }
        
        winner, reason = arb.arbitrate([low_conf, high_conf], contested_resource="page-1")
        assert winner["agent"] == "technical_intelligence"
        assert "confidence" in reason

    def test_arbitrate_by_cost(self):
        arb = ArbitrationEngine()
        
        high_cost = {
            "agent": "content_intelligence",
            "action": "content_generator",
            "risk_level": "normal",
            "confidence": 0.8,
            "cost": 5.0,
        }
        low_cost = {
            "agent": "seo_intelligence",
            "action": "seo_audit",
            "risk_level": "normal",
            "confidence": 0.8,
            "cost": 1.0,
        }
        
        winner, reason = arb.arbitrate([high_cost, low_cost], contested_resource="page-1")
        assert winner["agent"] == "seo_intelligence"
        assert "cost" in reason


class TestConsensusEngine:
    def test_consensus_approval(self):
        engine = ConsensusEngine()
        intelligences = [SeoIntelligence(), ContentIntelligence(), TechnicalIntelligence()]
        
        proposal = {"action": "seo_audit_run", "confidence": 0.9}
        approved, ratio = engine.gather_consensus(intelligences, proposal)
        assert approved is True
        assert ratio >= 0.5


class TestLoadBalancer:
    def test_route_task_picks_efficient(self):
        lb = LoadBalancer()
        intelligences = [SeoIntelligence(), TechnicalIntelligence()]
        
        # Both support seo-related capabilities, but SeoIntelligence is cheaper/faster
        winner = lb.route_task("technical_seo_audit", intelligences)
        assert winner is not None
        assert winner.name == "seo_intelligence"
