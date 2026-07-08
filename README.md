# Website Orchestrator

> Autonomous Enterprise Intelligence Platform & SaaS Experience

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-818%20passing-brightgreen.svg)](tests)

## Overview

The Website Orchestrator is a production-grade enterprise SaaS platform designed to automate high-scale search engine optimization, content publishing, and continuous performance tuning. By integrating a React-based multi-tenant experience layer with a multi-layered agentic AI planning stack (Milestones 1–7), the platform enables organizations to run autonomous growth campaigns safely under strict human-in-the-loop governance.

---

## Architectural Systems

The platform consists of seven intelligence layers and a robust SaaS experience surface:

### 1. Core Platform (Milestone 1)
Crawler, Digital Twin Postgres schema, Check Engine, Fix Generator, and Publishing Adapters (WordPress client).

### 2. Intelligence Layer (Milestone 2)
Knowledge Objects, AI Providers Registry, versioned Prompt Framework, and cryptographically signed AI Audits.

### 3. SEO Intelligence (Milestone 3)
10 SEO Engines (Analytics, Local SEO, Keyword Tracking, Reputation, etc.), Engine Registry, and Topical Authority graphs.

### 4. Growth Platform (Milestone 4)
10 Growth Engines, Automation, Agency Management systems, and Role-Based Access Control (RBAC).

### 5. Unified Brain (Milestone 5)
Knowledge Graph, Decision Engine, Platform Providers, and AI Copilot.

### 6. Agentic AI (Milestone 6)
Goal Engine, Planner, Reasoner, Cognitive Memory manager (7 systems: short-term, working, episodic, semantic, procedural, long-term, reflective), Agentic Runtime, and Governance Gate.

### 7. Autonomous Enterprise Intelligence (Milestone 7)
Continuous Observation EventBus and EventStore, Enterprise Knowledge Graph, autonomous Goal Generator, Workflow Intelligence, self-optimizing cost routing, and grounded Executive briefing compilers.

### 8. SaaS Experience Layer (SaaS Platform)
AI Workspace, Enterprise Platform (SSO/SCIM/OIDC/Billing), Analytics dashboards, Automation Studio visual Flow builders, Collaboration Threads, and Design System components.

---

## Package Structure

```
Website-Orchestrator/
├── packages/
│   ├── core/                  # Dependency-free leaf utilities and config settings.
│   ├── crawler/               # Polite same-domain web crawler.
│   ├── digital_twin/          # PostgreSQL database models.
│   ├── check_engine/          # Rule-based issue detector (thin content, broken links).
│   ├── fix_generator/         # Suggested fix generators.
│   ├── publishing_adapter/    # WordPress REST API integration client.
│   ├── governance/            # Approval workflow rules and rollback engine.
│   ├── api/                   # FastAPI gateway composition root.
│   ├── brain/                 # Cognitive Knowledge Graph and Decision Engine.
│   ├── agentic/               # Goal Planner, Reasoner, and runtime memory.
│   ├── enterprise_intelligence/ # EventBus, drift/trend checkers, and strategy forecast.
│   ├── saas/                  # Multi-tenant billing, SCIM, and workspace tables.
│   └── design-system/         # HSL styling design tokens and React components.
└── apps/
    ├── api/                   # CLI runner scripts.
    ├── web-workspace/         # Workspace Spatial Canvas React client.
    ├── web-admin/             # RBAC and Subscription settings React application.
    ├── web-analytics/         # Metrics rollup query builder React application.
    ├── web-automation/        # Webhook logs and approval queues React application.
    └── web-collab/            # Live avatars list and alerts React application.
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Saikumargoudkandunuri/Website-Orchestrator.git
   cd Website-Orchestrator
   ```

2. **Install Python backend dependencies**
   ```bash
   uv sync
   ```

3. **Start PostgreSQL database and Redis**
   ```bash
   docker-compose up -d
   ```

4. **Initialize databases schemas**
   ```bash
   cd packages/digital_twin
   uv run alembic upgrade head
   ```

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your local credentials
   ```

---

## Running Tests

### Run Backend Pytest Suite
```bash
uv run pytest
```
*Executes all 818 unit, property, and integration tests across M1–M7 and SaaS packages.*

### Run Frontend Vitest Suites
```bash
# Workspace Client Tests
cd apps/web-workspace && npx vitest run

# Admin Client Tests
cd apps/web-admin && npx vitest run

# Analytics Client Tests
cd apps/web-analytics && npx vitest run

# Automation Client Tests
cd apps/web-automation && npx vitest run

# Collaboration Client Tests
cd apps/web-collab && npx vitest run
```

---

## Operational Tools & Quality Gates

### Code Quality Check
```bash
# Format and Lint check
uv run ruff check packages/
uv run ruff format packages/

# Strict Type check
uv run mypy packages/
```

### Static Compilation Check
```bash
uv run python -m compileall -q packages apps
```

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

