from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app import create_app
from api.container import Subsystems
from check_engine import CheckEngine
from crawler import Crawler
from fix_generator import FixGenerator
from growth.api import build_growth_container
from growth.db import create_growth_tables


class DummyTwin:
    def list_active_issues(self, tenant_id):
        return []

    def list_fixes(self, tenant_id):
        return []

    def list_audit_entries(self, tenant_id):
        return []

    def get_fix(self, tenant_id, fix_id):
        return None


class DummyGovernance:
    def approve_fix(self, *args):
        raise AssertionError("not used by growth tests")

    def reject_fix(self, *args):
        raise AssertionError("not used by growth tests")

    def rollback_fix(self, *args):
        raise AssertionError("not used by growth tests")


def _client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_growth_tables(engine)
    session_factory = sessionmaker(bind=engine)
    growth = build_growth_container(session_factory, "tenant-test")
    subsystems = Subsystems(
        crawler=Crawler(),
        digital_twin=DummyTwin(),
        check_engine=CheckEngine(),
        fix_generator=FixGenerator(),
        governance=DummyGovernance(),
        tenant_id="tenant-test",
    )
    return TestClient(create_app(subsystems=subsystems, growth=growth))


def test_growth_local_seo_report_is_mounted_persisted_and_readable() -> None:
    client = _client()

    response = client.post(
        "/growth/local-seo/sites/site-a/analyze",
        json={
            "pages_with_contact_data": [
                {
                    "page_id": "home",
                    "schema_blocks": [
                        {
                            "type": "LocalBusiness",
                            "name": "Acme Services",
                            "telephone": "+1-555-0100",
                            "address": {"streetAddress": "1 Main Street"},
                        }
                    ],
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["site_id"] == "site-a"
    assert response.json()["nap_consistency"]["is_consistent"] is True

    latest = client.get("/growth/local-seo/sites/site-a/reports/latest")
    assert latest.status_code == 200
    assert latest.json()["version"] == 1


def test_growth_health_reports_configured_services() -> None:
    client = _client()

    response = client.get("/growth/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["tenant_id"] == "tenant-test"
    assert body["services"]["agency_management"] is True
    assert all(body["services"].values())


def test_growth_rank_tracking_capture_and_report_flow() -> None:
    client = _client()

    keyword = client.post(
        "/growth/rank-tracking/sites/site-a/keywords",
        json={"keyword": "example seo", "page_id": "page-1", "geo": "US"},
    )
    assert keyword.status_code == 200
    assert keyword.json()["keyword"] == "example seo"

    capture = client.post(
        "/growth/rank-tracking/sites/site-a/capture",
        json={"device": "desktop", "geo": "US"},
    )
    assert capture.status_code == 200
    assert len(capture.json()) == 1

    report = client.get("/growth/rank-tracking/sites/site-a/report")
    assert report.status_code == 200
    assert report.json()["snapshot_count"] == 1
    assert report.json()["visibility_trend"]["series"]


def test_growth_automation_rule_dispatch_is_logged() -> None:
    client = _client()

    rule = client.post(
        "/growth/automation/rules",
        json={
            "id": "rule-critical-issue",
            "name": "Notify on critical issue",
            "trigger_event_type": "issue.critical_detected",
            "condition": {"field": "severity", "operator": "eq", "value": "critical"},
            "action": {
                "action_type": "notify",
                "channel": "in_app",
                "recipient_ref": "owner",
                "message_template": "Critical issue detected",
            },
            "site_id": "site-a",
        },
    )
    assert rule.status_code == 200

    event = client.post(
        "/growth/automation/events",
        json={
            "event_type": "issue.critical_detected",
            "site_id": "site-a",
            "payload": {"severity": "critical"},
        },
    )
    assert event.status_code == 200

    logs = client.get("/growth/automation/sites/site-a/execution-log")
    assert logs.status_code == 200
    assert logs.json()[0]["rule_id"] == "rule-critical-issue"
    assert logs.json()[0]["result"] == "success"


def test_growth_agency_management_crud_flow() -> None:
    client = _client()

    org = client.post(
        "/growth/agency/organizations",
        json={
            "organization_id": "org-a",
            "name": "Agency A",
            "branding": {"primary_color": "#123456"},
        },
    )
    assert org.status_code == 200
    assert org.json()["organization_id"] == "org-a"

    assert client.get("/growth/agency/organizations/org-a").json()["name"] == "Agency A"

    client_response = client.post(
        "/growth/agency/organizations/org-a/clients",
        json={
            "client_id": "client-a",
            "name": "Client A",
            "contact_email": "owner@example.com",
        },
    )
    assert client_response.status_code == 200
    assert client_response.json()["contact_email"] == "owner@example.com"

    clients = client.get("/growth/agency/organizations/org-a/clients")
    assert clients.status_code == 200
    assert clients.json()[0]["client_id"] == "client-a"

    team = client.post(
        "/growth/agency/organizations/org-a/teams",
        json={"team_id": "team-a", "name": "SEO Team", "members": ["user-a"]},
    )
    assert team.status_code == 200
    assert team.json()["members"] == ["user-a"]

    workspace = client.post(
        "/growth/agency/workspaces",
        json={
            "workspace_id": "workspace-a",
            "organization_id": "org-a",
            "user_id": "user-a",
            "name": "Weekly view",
            "client_refs": ["client-a"],
            "site_refs": ["site-a"],
            "pinned_dashboards": ["rankings"],
        },
    )
    assert workspace.status_code == 200
    assert workspace.json()["site_refs"] == ["site-a"]

    task = client.post(
        "/growth/agency/tasks",
        json={
            "task_id": "task-a",
            "organization_id": "org-a",
            "client_id": "client-a",
            "title": "Fix title tag",
            "description": "Apply recommendation",
            "referenced_finding_id": "finding-a",
            "assignee_id": "user-a",
        },
    )
    assert task.status_code == 200
    assert task.json()["status"] == "open"

    updated = client.patch(
        "/growth/agency/tasks/task-a/status",
        json={"status": "completed"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"

    notification = client.post(
        "/growth/agency/notifications",
        json={
            "notification_id": "notification-a",
            "organization_id": "org-a",
            "recipient_id": "user-a",
            "channel": "in_app",
            "message": "Task completed",
            "status": "sent",
        },
    )
    assert notification.status_code == 200
    assert notification.json()["message"] == "Task completed"

    notifications = client.get("/growth/agency/notifications/user-a")
    assert notifications.status_code == 200
    assert notifications.json()[0]["notification_id"] == "notification-a"
