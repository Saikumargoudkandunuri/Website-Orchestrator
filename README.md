# Website Orchestrator

> Self-hosted, zero-budget, AI-assisted website operations platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-398%20passing-brightgreen.svg)](tests)

## Overview

The Website Orchestrator is a self-hosted platform for automated website operations. **Milestone 0** ("Prove the loop") establishes the foundational end-to-end operational loop for a single WordPress site with human-approved changes and deterministic checks.

### Core Principle

**The live website is never modified directly.** Every write passes through a Publishing Adapter and only after explicit human approval through a Governance layer.

## Key Features

- 🔍 **Polite Crawling**: Same-domain crawling with robots.txt compliance and configurable rate limiting
- 🔎 **Deterministic Checks**: Rule-based issue detection (missing titles, thin content, broken links, redirect chains, missing alt text)
- 🛠️ **Smart Fix Generation**: Automatic generation of suggested fixes with clear applicability flags
- ✅ **Human-in-the-Loop Governance**: Every change requires explicit approval with full audit trail
- 🔄 **Safe Rollback**: Reliable rollback of applied changes with before/after value tracking
- 🏗️ **Digital Twin**: PostgreSQL-backed structured representation of crawled sites with freshness metadata
- 🔐 **Security First**: Secrets isolated from code, credential redaction in logs, fail-closed error handling
- 📊 **Multi-Tenant Ready**: All tables include tenant_id from day one
- 🧪 **Property-Based Testing**: 398 comprehensive tests covering correctness properties

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      API Surface (FastAPI)                   │
│         /crawl  /issues  /fixes  /audit-log  /docs          │
└──────────────────────┬──────────────────────────────────────┘
                       │
         ┌─────────────┴────────────────┐
         │                              │
┌────────▼────────┐          ┌─────────▼─────────┐
│  Crawler        │          │  Governance Layer  │
│  (discovery)    │          │  (approve/reject)  │
└────────┬────────┘          └─────────┬─────────┘
         │                              │
┌────────▼────────┐          ┌─────────▼─────────┐
│  Digital Twin   │◄────────►│ Publishing Adapter│
│  (PostgreSQL)   │          │  (WordPress API)  │
└────────┬────────┘          └───────────────────┘
         │
┌────────▼────────┐          ┌───────────────────┐
│  Check Engine   │          │  Fix Generator    │
│  (detect issues)│─────────►│  (create fixes)   │
└─────────────────┘          └───────────────────┘
```

### Package Structure

```
Website-Orchestrator/
├── packages/
│   ├── core/              # Shared types, exceptions, interfaces (dependency-free)
│   ├── crawler/           # Same-domain web crawler
│   ├── digital_twin/      # PostgreSQL models and repository
│   ├── check_engine/      # Deterministic issue detection
│   ├── fix_generator/     # Suggested fix generation
│   ├── publishing_adapter/# WordPress REST API client
│   ├── governance/        # Approval workflow and audit trail
│   ├── api/              # FastAPI HTTP surface
│   ├── ai_generator/     # (Future: LLM integration)
│   ├── intelligence/     # (Future: AI-powered analysis)
│   ├── engines/          # (Future: Advanced SEO engines)
│   └── growth/           # (Future: Growth and analytics)
└── apps/
    └── e2e/              # End-to-end proof-of-loop tests
```

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/Website-Orchestrator.git
   cd Website-Orchestrator
   ```

2. **Install uv** (if not already installed)
   ```bash
   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. **Install dependencies**
   ```bash
   uv sync
   ```

4. **Start PostgreSQL**
   ```bash
   docker-compose up -d
   ```

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

6. **Run database migrations**
   ```bash
   cd packages/digital_twin
   uv run alembic upgrade head
   ```

### Configuration

Edit `.env` with your settings:

```bash
# Database (matches docker-compose.yml)
DATABASE_URL=postgresql+psycopg://orchestrator:orchestrator@localhost:5432/orchestrator

# Multi-tenancy
TENANT_ID=default

# WordPress target
WP_BASE_URL=https://your-wordpress-site.example
WP_USERNAME=your-wp-username
WP_APPLICATION_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

⚠️ **Never commit `.env` to source control!** It contains secrets.

## Running Tests

### Run all tests
```bash
uv run pytest
```

### Run specific test categories
```bash
# Property-based tests only
uv run pytest -m property

# End-to-end tests only
uv run pytest -m e2e

# Specific package tests
uv run pytest packages/crawler/tests/
```

### Run with coverage
```bash
uv run pytest --cov=packages --cov-report=html
```

## Usage

### Start the API server

```bash
cd packages/api
uv run uvicorn api.app:app --reload
```

The API will be available at `http://localhost:8000` with automatic documentation at `http://localhost:8000/docs`.

### Workflow Example

#### 1. Crawl a site
```bash
curl -X POST http://localhost:8000/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "start_url": "https://example.com",
    "max_pages": 50
  }'
```

Response includes:
- Pages crawled count
- Issues detected (grouped by type)
- Auto-applicable vs report-only fix counts

#### 2. Review detected issues
```bash
curl http://localhost:8000/issues
```

#### 3. Review suggested fixes
```bash
curl http://localhost:8000/fixes
```

#### 4. Approve an auto-applicable fix
```bash
curl -X POST http://localhost:8000/fixes/123/approve \
  -H "Content-Type: application/json" \
  -d '{
    "actor": "admin@example.com",
    "rationale": "Missing alt text fix looks good"
  }'
```

#### 5. View audit trail
```bash
curl http://localhost:8000/audit-log
```

#### 6. Rollback if needed
```bash
curl -X POST http://localhost:8000/fixes/123/rollback \
  -H "Content-Type: application/json" \
  -d '{
    "actor": "admin@example.com",
    "rationale": "Reverting due to user feedback"
  }'
```

## Issue Detection

The Check Engine detects the following issues:

| Issue Type | Severity | Auto-Applicable | Description |
|------------|----------|----------------|-------------|
| **missing_title** | High | ❌ Report-only | Page has no title tag |
| **missing_meta_description** | Medium | ❌ Report-only | Page has no meta description |
| **thin_content** | Medium | ❌ Report-only | Content below 300 words |
| **missing_alt_text** | Medium | ✅ Auto-applicable* | Image missing alt text |
| **broken_links** | High | ❌ Report-only | Link returns 4xx/5xx status |
| **redirect_chains** | Low | ❌ Report-only | 3+ redirects in chain |
| **duplicate_titles** | Medium | ❌ Report-only | Multiple pages share title |

*Auto-applicable only when media ID can be extracted from HTML

## Governance and Audit Trail

Every decision creates an audit trail entry with:
- **Actor**: Human identifier (email, username)
- **Rationale**: Why the decision was made
- **Timestamp**: When it occurred
- **Status transition**: pending → approved → applied → rolled_back

All governance operations are **fail-closed**: if anything goes wrong, the operation is denied and no change is applied.

## Security

- ✅ All secrets loaded from environment variables
- ✅ Credentials never logged at any severity level
- ✅ WordPress Application Password (not login password) for auth
- ✅ All errors strip credentials before being raised
- ✅ Missing secrets fail startup with safe error messages
- ✅ Multi-tenancy enforced at database level

## Development

### Adding a new check

1. Add check logic to `packages/check_engine/check_engine/checks.py`
2. Add tests to `packages/check_engine/tests/`
3. Update the check aggregator
4. Add fix mapping in `packages/fix_generator/fix_generator/generator.py`

### Adding a new fix type

1. Update `FixType` enum in `packages/core/core/types.py`
2. Add generation logic in Fix Generator
3. Add Publishing Adapter method if auto-applicable
4. Add governance handling
5. Write property-based tests

### Code Quality

```bash
# Run linters
uv run ruff check packages/

# Format code
uv run ruff format packages/

# Type checking
uv run mypy packages/
```

## Database Schema

Key tables (all include `tenant_id`):

- **pages**: Crawled page metadata with freshness timestamp
- **links**: Extracted links between pages
- **issues**: Detected issues with ignore flag
- **suggested_fixes**: Generated fixes with status and applicability
- **audit_trail**: Complete governance decision log

### Running Migrations

```bash
cd packages/digital_twin
uv run alembic revision --autogenerate -m "Description"
uv run alembic upgrade head
```

## Observability

All logs are emitted as structured JSON:
```json
{
  "timestamp": "2024-01-15T10:30:45Z",
  "level": "INFO",
  "message": "Fix approved",
  "trace_id": "abc-123-def",
  "fix_id": 42,
  "actor": "admin@example.com"
}
```

Trace IDs allow correlation of all logs for a single operation.

## Roadmap

### Milestone 0 ✅ (Current)
- [x] End-to-end loop with human approval
- [x] Deterministic checks only
- [x] WordPress alt text updates
- [x] Full audit trail

### Milestone 1 (Planned)
- [ ] LLM-powered content analysis
- [ ] Meta description generation
- [ ] AI-driven alt text suggestions
- [ ] Schema.org / JSON-LD generation

### Milestone 2 (Future)
- [ ] Multi-site orchestration
- [ ] Advanced SEO intelligence engines
- [ ] Analytics and rank tracking
- [ ] Content optimization recommendations

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`uv run pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Contribution Guidelines

- All new features must include tests
- Maintain the Core Package dependency direction (dependencies point inward)
- Follow the existing code style
- Update documentation for user-facing changes
- Keep commits atomic and well-described

## Testing Philosophy

This project uses **property-based testing** with Hypothesis to verify correctness properties rather than just example-based testing. Each test is derived from a design requirement and validates that the requirement holds across a wide range of inputs.

Example property:
> "WHEN the crawler reaches max_pages, it SHALL stop retrieving"

This becomes a test that generates random valid inputs and verifies the property holds for all of them.

## Troubleshooting

### PostgreSQL connection fails
```bash
# Check if PostgreSQL is running
docker-compose ps

# View logs
docker-compose logs postgres

# Restart services
docker-compose restart
```

### Tests fail on Windows
Line ending differences are normal. The warnings about LF → CRLF can be ignored.

### Missing secrets error
Check that `.env` exists and contains all required variables from `.env.example`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM and database toolkit
- [Alembic](https://alembic.sqlalchemy.org/) - Database migrations
- [Hypothesis](https://hypothesis.readthedocs.io/) - Property-based testing
- [uv](https://docs.astral.sh/uv/) - Fast Python package manager

## Support

- Documentation: [Coming soon]
- Issues: [GitHub Issues](https://github.com/yourusername/Website-Orchestrator/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/Website-Orchestrator/discussions)

---

**Note**: This is Milestone 0 - a proof of concept. The platform is under active development and APIs may change.
