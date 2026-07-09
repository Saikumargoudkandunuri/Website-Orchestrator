/* ============================================================
   API Client — Typed wrapper for all backend endpoints
   ============================================================ */

const BASE = '';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

function qs(params: Record<string, string>): string {
  return '?' + new URLSearchParams(params).toString();
}

const TENANT = 'demo-tenant';
const USER_ID = 'demo-user';

/* ---------- Core Platform (M1–M7) ---------- */

export interface CrawlRequest {
  start_url: string;
  max_pages: number;
}

export interface CrawlSummary {
  pages_crawled: number;
  issues_found: number;
  fixes_generated: number;
}

export interface Issue {
  id: string;
  url: string;
  category: string;
  severity: string;
  description: string;
  detected_at: string;
}

export interface SuggestedFix {
  id: string;
  issue_id: string;
  description: string;
  diff: string;
  status: string;
  reviewed_by?: string;
}

export interface AuditEntry {
  id: string;
  action: string;
  actor: string;
  timestamp: string;
  detail: string;
}

export const coreApi = {
  crawl: (data: CrawlRequest) => request<CrawlSummary>('/crawl', { method: 'POST', body: JSON.stringify(data) }),
  listIssues: () => request<Issue[]>('/issues'),
  listFixes: () => request<SuggestedFix[]>('/fixes'),
  approveFix: (id: string, reason: string) => request<SuggestedFix>(`/fixes/${id}/approve`, { method: 'POST', body: JSON.stringify({ approved_by: USER_ID, reason }) }),
  rejectFix: (id: string, reason: string) => request<SuggestedFix>(`/fixes/${id}/reject`, { method: 'POST', body: JSON.stringify({ approved_by: USER_ID, reason }) }),
  rollbackFix: (id: string, reason: string) => request<SuggestedFix>(`/fixes/${id}/rollback`, { method: 'POST', body: JSON.stringify({ approved_by: USER_ID, reason }) }),
  listAuditLog: () => request<AuditEntry[]>('/audit-log'),
};

/* ---------- Agentic Platform ---------- */

export const agenticApi = {
  memory: {
    listGoals: () => request<Record<string, unknown>[]>('/agentic/memory/goals'),
    saveGoal: (data: Record<string, unknown>) => request<Record<string, unknown>>('/agentic/memory/goals', { method: 'POST', body: JSON.stringify(data) }),
    getGoal: (id: string) => request<Record<string, unknown>>(`/agentic/memory/goals/${id}`),
    listEpisodes: () => request<Record<string, unknown>[]>('/agentic/memory/episodes'),
    listReflections: () => request<Record<string, unknown>[]>('/agentic/memory/reflections'),
    listProcedures: () => request<Record<string, unknown>[]>('/agentic/memory/procedures'),
    search: (query: string) => request<Record<string, unknown>[]>(`/agentic/memory/search${qs({ query })}`),
  },
  runtime: {
    start: (executionId: string, plan: Record<string, unknown>) => request<Record<string, unknown>>(`/agentic/runtime/start${qs({ execution_id: executionId })}`, { method: 'POST', body: JSON.stringify(plan) }),
    pause: (executionId: string) => request<Record<string, unknown>>(`/agentic/runtime/pause${qs({ execution_id: executionId })}`, { method: 'POST' }),
    resume: (executionId: string) => request<Record<string, unknown>>(`/agentic/runtime/resume${qs({ execution_id: executionId })}`, { method: 'POST' }),
    cancel: (executionId: string) => request<Record<string, unknown>>(`/agentic/runtime/cancel${qs({ execution_id: executionId })}`, { method: 'POST' }),
    getExecution: (executionId: string) => request<Record<string, unknown>>(`/agentic/runtime/${executionId}`),
    getHistory: (executionId: string) => request<Record<string, unknown>[]>(`/agentic/runtime/${executionId}/history`),
    getMetrics: (executionId: string) => request<Record<string, unknown>[]>(`/agentic/runtime/${executionId}/metrics`),
    step: (executionId: string) => request<Record<string, unknown>>(`/agentic/runtime/step${qs({ execution_id: executionId })}`, { method: 'POST' }),
  },
  reflection: {
    run: (executionId: string, steps: Record<string, unknown>[]) => request<Record<string, unknown>>(`/agentic/reflection/run${qs({ execution_id: executionId })}`, { method: 'POST', body: JSON.stringify(steps) }),
    get: (executionId: string) => request<Record<string, unknown>>(`/agentic/reflection/${executionId}`),
    getProviderScores: () => request<Record<string, unknown>[]>('/agentic/learning/provider-scores'),
    getToolScores: () => request<Record<string, unknown>[]>('/agentic/learning/tool-scores'),
  },
  learning: {
    providerScores: () => request<Record<string, unknown>[]>('/agentic/learning/provider-scores'),
    toolScores: () => request<Record<string, unknown>[]>('/agentic/learning/tool-scores'),
    experience: () => request<Record<string, unknown>>('/agentic/learning/experience'),
    confidence: (category: string) => request<Record<string, unknown>>(`/agentic/learning/confidence${qs({ category })}`),
  },
  missions: {
    start: (goalId: string, objective: string) => request<Record<string, unknown>>(`/agentic/missions${qs({ goal_id: goalId, objective })}`, { method: 'POST' }),
    get: (missionId: string) => request<Record<string, unknown>>(`/agentic/missions/${missionId}`),
    pause: (missionId: string) => request<Record<string, unknown>>(`/agentic/missions/${missionId}/pause`, { method: 'POST' }),
    resume: (missionId: string) => request<Record<string, unknown>>(`/agentic/missions/${missionId}/resume`, { method: 'POST' }),
    cancel: (missionId: string) => request<Record<string, unknown>>(`/agentic/missions/${missionId}/cancel`, { method: 'POST' }),
    agents: (missionId: string) => request<Record<string, unknown>[]>(`/agentic/missions/${missionId}/agents`),
    blackboard: (missionId: string) => request<Record<string, unknown>[]>(`/agentic/missions/${missionId}/blackboard`),
    messages: (missionId: string) => request<Record<string, unknown>[]>(`/agentic/missions/${missionId}/messages`),
    metrics: (missionId: string) => request<Record<string, unknown>[]>(`/agentic/missions/${missionId}/metrics`),
  },
};

/* ---------- SaaS Platform (v1) ---------- */

export interface Workspace {
  id: string;
  name: string;
  tenant_id: string;
  canvases: unknown[];
}

export interface CanvasNode {
  id: string;
  node_type: string;
  label: string;
  x: number;
  y: number;
  properties: Record<string, unknown>;
}

export const workspaceApi = {
  list: () => request<Workspace[]>(`/v1/workspaces${qs({ tenant_id: TENANT })}`),
  createNode: (workspaceId: string, data: { canvas_id: string; node_type: string; label: string; x: number; y: number }) =>
    request<CanvasNode>(`/v1/workspaces/${workspaceId}/canvas/nodes${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify(data) }),
  deleteNode: (workspaceId: string, nodeId: string, canvasId: string) =>
    request<{ deleted: boolean }>(`/v1/workspaces/${workspaceId}/canvas/nodes/${nodeId}${qs({ canvas_id: canvasId, tenant_id: TENANT })}`, { method: 'DELETE' }),
  searchCommands: (query?: string) => request<Record<string, unknown>[]>(`/v1/workspaces/commands${qs({ query: query || '' })}`),
};

export const analyticsApi = {
  getDashboard: (id: string) => request<Record<string, unknown>>(`/v1/analytics/dashboards/${id}${qs({ tenant_id: TENANT })}`),
  query: (metric: string, start: string, end: string) =>
    request<Record<string, unknown>[]>(`/v1/analytics/query${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify({ metric_name: metric, start_time: start, end_time: end, aggregation: 'avg', interval: '1h' }) }),
  exportReport: (format: string, metrics: string[]) =>
    request<unknown>(`/v1/analytics/exports${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify({ format, metric_names: metrics }) }),
  listAlerts: () => request<Record<string, unknown>[]>(`/v1/analytics/alerts${qs({ tenant_id: TENANT })}`),
  createAlert: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/v1/analytics/alerts${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify(data) }),
};

export const automationApi = {
  createWorkflow: (data: { name: string; description: string; trigger_type: string; steps: unknown[] }) =>
    request<Record<string, unknown>>(`/v1/automation/workflows${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify(data) }),
  getWorkflow: (id: string) => request<Record<string, unknown>>(`/v1/automation/workflows/${id}${qs({ tenant_id: TENANT })}`),
  resumeExecution: (id: string, signal: string) =>
    request<Record<string, unknown>>(`/v1/automation/executions/${id}/resume${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify({ signal }) }),
  getTrace: (id: string) => request<Record<string, unknown>>(`/v1/automation/executions/${id}/trace${qs({ tenant_id: TENANT })}`),
};

export const collabApi = {
  createThread: (data: { title: string; target_node_id: string; created_by: string }) =>
    request<Record<string, unknown>>(`/v1/collab/threads${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify(data) }),
  listThreads: (targetNodeId: string) =>
    request<Record<string, unknown>[]>(`/v1/collab/threads${qs({ target_node_id: targetNodeId, tenant_id: TENANT })}`),
  addComment: (threadId: string, data: { author_id: string; body: string }) =>
    request<Record<string, unknown>>(`/v1/collab/threads/${threadId}/comments${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify(data) }),
  listComments: (threadId: string) =>
    request<Record<string, unknown>[]>(`/v1/collab/threads/${threadId}/comments${qs({ tenant_id: TENANT })}`),
  listDecisions: () => request<Record<string, unknown>[]>(`/v1/collab/decisions${qs({ tenant_id: TENANT })}`),
  listNotifications: () => request<Record<string, unknown>[]>(`/v1/collab/notifications${qs({ user_id: USER_ID, tenant_id: TENANT })}`),
};

export const copilotApi = {
  chat: (message: string, context?: Record<string, unknown>) =>
    request<Record<string, string>>(`/v1/copilot/chat${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify({ message, context: context || {} }) }),
  getReasoning: (goalId: string) =>
    request<Record<string, unknown>>(`/v1/copilot/reasoning/${goalId}${qs({ tenant_id: TENANT })}`),
  listPrompts: () => request<Record<string, unknown>[]>(`/v1/copilot/prompts${qs({ tenant_id: TENANT })}`),
  createPrompt: (data: { name: string; template: string; variables: string[] }) =>
    request<Record<string, unknown>>(`/v1/copilot/prompts${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify(data) }),
};

export const enterpriseApi = {
  createOrg: (data: { name: string; slug: string; plan: string }) =>
    request<Record<string, unknown>>('/v1/enterprise/orgs', { method: 'POST', body: JSON.stringify(data) }),
  getAuditLogs: (orgId: string) =>
    request<Record<string, unknown>[]>(`/v1/enterprise/orgs/${orgId}/audit-logs${qs({ tenant_id: TENANT })}`),
  assignRole: (orgId: string, data: { user_id: string; role: string }) =>
    request<Record<string, unknown>>(`/v1/enterprise/orgs/${orgId}/roles${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify(data) }),
  getUsage: () => request<Record<string, number>>(`/v1/enterprise/billing/usage${qs({ tenant_id: TENANT })}`),
  createSubscription: (orgId: string, data: { plan: string; billing_cycle: string }) =>
    request<Record<string, unknown>>(`/v1/enterprise/billing/subscriptions${qs({ org_id: orgId })}`, { method: 'POST', body: JSON.stringify(data) }),
  scimCreateUser: (data: { userName: string; emails: { value: string; primary: boolean }[] }) =>
    request<Record<string, unknown>>('/v1/enterprise/scim/v2/Users', { method: 'POST', body: JSON.stringify(data) }),
};

export const marketplaceApi = {
  listApps: () => request<Record<string, unknown>[]>('/v1/marketplace/apps'),
  registerApp: (developerId: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/v1/developer/apps${qs({ developer_id: developerId })}`, { method: 'POST', body: JSON.stringify(data) }),
  installApp: (data: { app_id: string }) =>
    request<Record<string, unknown>>(`/v1/marketplace/install${qs({ tenant_id: TENANT })}`, { method: 'POST', body: JSON.stringify(data) }),
};
