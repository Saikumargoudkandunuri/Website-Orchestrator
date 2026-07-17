"""Onboarding HTTP boundary schemas (Pydantic v2).

Request/response models for the onboarding REST API. These validate input at the
boundary and shape the JSON returned to clients. They never duplicate the shared
Core_Package records; they describe the onboarding-specific resources.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

__all__ = [
    "Environment",
    "WebsiteStatus",
    "WebsiteType",
    "ConnectionType",
    "DetectionConfidence",
    "ApprovalMode",
    "WorkspaceCreate",
    "WorkspaceUpdate",
    "WorkspaceRead",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectRead",
    "WebsiteGroupCreate",
    "WebsiteGroupRead",
    "WebsiteCreate",
    "WebsiteUpdate",
    "WebsiteRead",
    "ConnectionCreate",
    "ConnectionVerifyRequest",
    "ConnectionRead",
    "IntegrationRead",
    "AgentConfig",
    "AgentSlot",
    "VerifyResult",
    "CrawlRequest",
    "BuildDigitalTwinRequest",
    "DashboardLive",
    "OnboardingAuditRead",
]


# --- Enumerations (architecture review #1, #2, #3, #15) -----------------------


class Environment(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    LOCALHOST = "localhost"
    PREVIEW = "preview"
    DEMO = "demo"


class WebsiteStatus(str, Enum):
    CONNECTED = "CONNECTED"
    VERIFYING = "VERIFYING"
    CRAWLING = "CRAWLING"
    INDEXING = "INDEXING"
    READY = "READY"
    ERROR = "ERROR"
    OFFLINE = "OFFLINE"
    DISABLED = "DISABLED"


class WebsiteType(str, Enum):
    WORDPRESS = "wordpress"
    SHOPIFY = "shopify"
    WEBFLOW = "webflow"
    FRAMER = "framer"
    NEXTJS = "nextjs"
    REACT = "react"
    VUE = "vue"
    LARAVEL = "laravel"
    STATIC_HTML = "static_html"
    CUSTOM_PHP = "custom_php"
    HEADLESS = "headless"
    UNKNOWN = "unknown"


class ConnectionType(str, Enum):
    WORDPRESS_REST = "wordpress_rest"
    WORDPRESS_APPLICATION_PASSWORD = "wordpress_application_password"
    WORDPRESS_OAUTH = "wordpress_oauth"
    SHOPIFY = "shopify"
    GITHUB = "github"
    SSH = "ssh"
    FTP = "ftp"
    SFTP = "sftp"
    CPLANE = "cpanel"
    PLESK = "plesk"
    CLOUDFLARE = "cloudflare"
    READ_ONLY = "read_only"
    HEADLESS = "headless"
    # Milestone 5 — the account-creation wizard collects every credential the
    # AI Digital Marketing Executive needs, once, up front. Each is stored
    # through the existing encrypted Connection row (never a new credential
    # store); ``connection_meta`` carries the provider name and any non-secret
    # identifiers (e.g. GA4 property id, GSC site URL).
    AI_PROVIDER = "ai_provider"
    GOOGLE_SEARCH_CONSOLE = "google_search_console"
    GOOGLE_ANALYTICS = "google_analytics"
    GOOGLE_BUSINESS_PROFILE = "google_business_profile"
    SEARCH_PROVIDER = "search_provider"
    EMAIL_PROVIDER = "email_provider"
    SOCIAL_PROVIDER = "social_provider"


class DetectionConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ApprovalMode(str, Enum):
    # Canonical governance vocabulary.
    ADVISORY = "advisory"
    APPROVAL = "approval"
    AUTONOMOUS = "autonomous"
    # Legacy values remain accepted for existing records/API clients.
    HUMAN = "human"
    AUTO = "auto"
    SCHEDULED = "scheduled"


# --- Agent configuration (architecture review #8) ----------------------------


class AgentSlot(BaseModel):
    """Per-agent configuration slot."""

    enabled: bool = False
    model: str | None = None
    provider: str | None = None
    temperature: float | None = None
    reasoning: bool = False


class AgentConfig(BaseModel):
    """Independent AI configuration for a single website."""

    planner: AgentSlot = Field(default_factory=AgentSlot)
    reviewer: AgentSlot = Field(default_factory=AgentSlot)
    editor: AgentSlot = Field(default_factory=AgentSlot)
    seo: AgentSlot = Field(default_factory=AgentSlot)
    analytics: AgentSlot = Field(default_factory=AgentSlot)
    crawler: AgentSlot = Field(default_factory=AgentSlot)
    publisher: AgentSlot = Field(default_factory=AgentSlot)
    memory: AgentSlot = Field(default_factory=AgentSlot)


# --- Workspace ----------------------------------------------------------------


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class WorkspaceRead(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime


# --- Project ------------------------------------------------------------------


class ProjectCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    archived: bool | None = None


class ProjectRead(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: str | None = None
    archived: bool
    created_at: datetime


# --- Website group ------------------------------------------------------------


class WebsiteGroupCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    description: str | None = None


class WebsiteGroupRead(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    name: str
    description: str | None = None
    created_at: datetime


# --- Website ------------------------------------------------------------------


class WebsiteCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)
    group_id: str | None = None
    name: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    display_name: str | None = None
    environment: Environment = Environment.PRODUCTION
    website_type: WebsiteType = WebsiteType.UNKNOWN

    @field_validator("url")
    @classmethod
    def _url_scheme(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("url must be non-blank")
        return value.strip()


class WebsiteUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    environment: Environment | None = None
    website_type: WebsiteType | None = None
    ai_enabled: bool | None = None
    automation_enabled: bool | None = None
    memory_enabled: bool | None = None
    approval_mode: ApprovalMode | None = None
    agent_config: AgentConfig | None = None


class WebsiteRead(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    project_id: str
    group_id: str | None = None
    name: str
    url: str
    display_name: str | None = None
    environment: str
    status: str
    website_type: str
    cms: str | None = None
    builder: str | None = None
    builder_version: str | None = None
    theme: str | None = None
    theme_version: str | None = None
    parent_theme: str | None = None
    child_theme: str | None = None
    framework: str | None = None
    wordpress_version: str | None = None
    php_version: str | None = None
    server: str | None = None
    hosting: str | None = None
    cdn: str | None = None
    waf: str | None = None
    rest_api_available: bool = False
    has_robots_txt: bool = False
    has_sitemap: bool = False
    has_rss: bool = False
    has_opengraph: bool = False
    has_schema: bool = False
    has_canonical: bool = False
    has_hreflang: bool = False
    plugins: list[Any] | None = None
    seo_plugins: list[Any] | None = None
    cache_plugins: list[Any] | None = None
    commerce_plugins: list[Any] | None = None
    analytics_plugins: list[Any] | None = None
    security_plugins: list[Any] | None = None
    forms_plugins: list[Any] | None = None
    membership_plugins: list[Any] | None = None
    performance_plugins: list[Any] | None = None
    language_plugins: list[Any] | None = None
    detection_confidence: str = "low"
    agent_config: dict | None = None
    ai_enabled: bool = False
    automation_enabled: bool = False
    memory_enabled: bool = False
    approval_mode: str = "human"
    onboarding_state: str = "created"
    last_crawled_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Connection ---------------------------------------------------------------


class ConnectionCreate(BaseModel):
    website_id: str = Field(..., min_length=1)
    connection_type: ConnectionType = ConnectionType.WORDPRESS_APPLICATION_PASSWORD
    # Plaintext credential — encrypted before persistence, never stored as-is.
    credential: str | None = None
    connection_meta: dict[str, Any] | None = None


class ConnectionVerifyRequest(BaseModel):
    website_id: str = Field(..., min_length=1)
    connection_type: ConnectionType = ConnectionType.WORDPRESS_APPLICATION_PASSWORD
    credential: str | None = None
    connection_meta: dict[str, Any] | None = None


class ConnectionRead(BaseModel):
    id: str
    tenant_id: str
    website_id: str
    connection_type: str
    connection_meta: dict | None = None
    capabilities: dict | None = None
    is_active: bool
    verified_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime


# --- Integration --------------------------------------------------------------


class IntegrationRead(BaseModel):
    id: str
    tenant_id: str
    website_id: str
    provider: str
    status: str
    last_sync: datetime | None = None
    expires_at: datetime | None = None
    quota_used: int | None = None
    quota_limit: int | None = None
    last_error: str | None = None
    integration_meta: dict | None = None
    created_at: datetime


# --- Verify result ------------------------------------------------------------


class VerifyResult(BaseModel):
    website_id: str
    connection_type: str
    status: str
    cms: str | None = None
    builder: str | None = None
    theme: str | None = None
    plugins: list[Any] | None = None
    capabilities: dict | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


# --- Crawl / digital twin -----------------------------------------------------


class CrawlRequest(BaseModel):
    website_id: str = Field(..., min_length=1)
    max_pages: int = Field(100, gt=0, le=10000)


class BuildDigitalTwinRequest(BaseModel):
    website_id: str = Field(..., min_length=1)


# --- Dashboard ----------------------------------------------------------------


class DashboardLive(BaseModel):
    website_id: str
    name: str
    url: str
    status: str
    environment: str
    builder: str | None = None
    theme: str | None = None
    cms: str | None = None
    plugins: list[Any] | None = None
    pages: int = 0
    posts: int = 0
    media: int = 0
    issues: int = 0
    pending_fixes: int = 0
    health_score: float | None = None
    seo_score: float | None = None
    performance_score: float | None = None
    accessibility_score: float | None = None
    last_crawl: datetime | None = None
    automation_status: str | None = None
    ai_status: str | None = None
    memory_status: str | None = None


# --- Audit --------------------------------------------------------------------


class OnboardingAuditRead(BaseModel):
    id: str
    tenant_id: str
    website_id: str | None = None
    actor_type: str
    actor_id: str
    action: str
    reason: str | None = None
    before_value: str | None = None
    after_value: str | None = None
    rollback_available: bool = False
    approval_required: bool = False
    execution_time_ms: int | None = None
    tokens_used: int | None = None
    model: str | None = None
    cost_usd: float | None = None
    created_at: datetime
