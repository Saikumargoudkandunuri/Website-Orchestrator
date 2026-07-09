import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { enterpriseApi } from '../api';
import { Building, ShieldCheck, UserCheck, Key, Plus, FileText, ClipboardList } from 'lucide-react';

export default function EnterprisePage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'orgs' | 'users' | 'roles' | 'compliance'>('orgs');
  
  // Organization States
  const [orgName, setOrgName] = useState('');
  const [orgSlug, setOrgSlug] = useState('');
  const [orgPlan, setOrgPlan] = useState('enterprise');
  
  // Role assignment States
  const [assignUser, setAssignUser] = useState('');
  const [assignRole, setAssignRole] = useState('editor');

  // SCIM User States
  const [scimUsername, setScimUsername] = useState('');
  const [scimEmail, setScimEmail] = useState('');

  // Queries - Load audit logs for demo org
  const orgId = 'demo-org';
  const { data: auditLogs = [], isLoading: loadingAudits } = useQuery<any[]>({
    queryKey: ['orgAuditLogs', orgId],
    queryFn: () => enterpriseApi.getAuditLogs(orgId),
  });

  // Mutations
  const createOrgMutation = useMutation({
    mutationFn: (data: { name: string; slug: string; plan: string }) => enterpriseApi.createOrg(data),
    onSuccess: () => {
      setOrgName('');
      setOrgSlug('');
      alert('Enterprise Organization registered successfully!');
    }
  });

  const assignRoleMutation = useMutation({
    mutationFn: (data: { user_id: string; role: string }) => enterpriseApi.assignRole(orgId, data),
    onSuccess: () => {
      setAssignUser('');
      alert('User role assignment completed successfully!');
    }
  });

  const createScimUserMutation = useMutation({
    mutationFn: (data: { userName: string; emails: { value: string; primary: boolean }[] }) =>
      enterpriseApi.scimCreateUser(data),
    onSuccess: () => {
      setScimUsername('');
      setScimEmail('');
      alert('Directory User provisioned via SCIM integration!');
    }
  });

  const handleCreateOrg = (e: React.FormEvent) => {
    e.preventDefault();
    if (!orgName.trim() || !orgSlug.trim()) return;
    createOrgMutation.mutate({ name: orgName, slug: orgSlug, plan: orgPlan });
  };

  const handleAssignRole = (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignUser.trim()) return;
    assignRoleMutation.mutate({ user_id: assignUser, role: assignRole });
  };

  const handleCreateScimUser = (e: React.FormEvent) => {
    e.preventDefault();
    if (!scimUsername.trim() || !scimEmail.trim()) return;
    createScimUserMutation.mutate({
      userName: scimUsername,
      emails: [{ value: scimEmail, primary: true }]
    });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">Enterprise Administration</h1>
          <p className="text-sm text-slate-400">Establish corporate organizations, manage directory users via SCIM, and trace compliance audits</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'orgs' ? ' active' : ''}`} onClick={() => setActiveTab('orgs')}>Organizations</button>
        <button className={`tab${activeTab === 'users' ? ' active' : ''}`} onClick={() => setActiveTab('users')}>Directory Sync (SCIM)</button>
        <button className={`tab${activeTab === 'roles' ? ' active' : ''}`} onClick={() => setActiveTab('roles')}>Access Roles</button>
        <button className={`tab${activeTab === 'compliance' ? ' active' : ''}`} onClick={() => setActiveTab('compliance')}>Compliance Audit</button>
      </div>

      {activeTab === 'orgs' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Create org form */}
          <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 xl:col-span-1">
            <div className="flex items-center gap-2">
              <Building className="h-4.5 w-4.5 text-violet-400" />
              <h2 className="text-sm font-semibold text-slate-200">Create Corporate Org</h2>
            </div>
            
            <form onSubmit={handleCreateOrg} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Organization Name</label>
                <input
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="e.g. Acme Corporation"
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Workspace Slug</label>
                <input
                  value={orgSlug}
                  onChange={(e) => setOrgSlug(e.target.value)}
                  placeholder="acme-corp"
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Corporate Tier</label>
                <select
                  value={orgPlan}
                  onChange={(e) => setOrgPlan(e.target.value)}
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-200"
                >
                  <option value="business">Business Pro</option>
                  <option value="enterprise">Corporate Enterprise</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={createOrgMutation.isPending}
                className="w-full btn btn-primary flex justify-center items-center gap-1.5 py-2 text-xs"
              >
                <Plus className="h-4 w-4" /> Save Organization
              </button>
            </form>
          </div>

          {/* Org details preview */}
          <div className="bg-slate-950/60 border border-white/[0.06] rounded-xl p-5 xl:col-span-2">
            <h2 className="text-sm font-semibold text-slate-200 mb-3">Enterprise Tenant Details</h2>
            <div className="bg-black/40 border border-white/[0.03] p-4 rounded-lg font-mono text-[11px] text-slate-400 space-y-2">
              <div>Tenant Scope ID: <span className="text-slate-300">demo-tenant</span></div>
              <div>SSO Federation: <span className="text-slate-500">Not configured (SAML/OIDC available)</span></div>
              <div>Active Workspaces: <span className="text-slate-300">3 Workspaces</span></div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'users' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Create user SCIM */}
          <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 xl:col-span-1">
            <div className="flex items-center gap-2">
              <UserCheck className="h-4.5 w-4.5 text-violet-400" />
              <h2 className="text-sm font-semibold text-slate-200">SCIM Directory Provisioning</h2>
            </div>

            <form onSubmit={handleCreateScimUser} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Username</label>
                <input
                  value={scimUsername}
                  onChange={(e) => setScimUsername(e.target.value)}
                  placeholder="e.g. alice.smith"
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Primary Email</label>
                <input
                  type="email"
                  value={scimEmail}
                  onChange={(e) => setScimEmail(e.target.value)}
                  placeholder="alice@acme.com"
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <button
                type="submit"
                disabled={createScimUserMutation.isPending}
                className="w-full btn btn-primary flex justify-center items-center gap-1.5 py-2 text-xs"
              >
                <Plus className="h-4 w-4" /> Provision Directory User
              </button>
            </form>
          </div>

          <div className="bg-slate-950/60 border border-white/[0.06] rounded-xl p-5 xl:col-span-2">
            <h2 className="text-sm font-semibold text-slate-200 mb-3">SCIM Directory Status</h2>
            <div className="bg-black/40 border border-white/[0.03] p-4 rounded-lg font-mono text-[11px] text-slate-400 space-y-2">
              <div>Sync Engine Status: <span className="text-emerald-400 font-bold">Active Connection</span></div>
              <div>SCIM Endpoint URL: <span className="text-slate-300">/v1/enterprise/scim/v2/Users</span></div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'roles' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Assign user roles */}
          <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 xl:col-span-1">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4.5 w-4.5 text-violet-400" />
              <h2 className="text-sm font-semibold text-slate-200">Assign Member Access</h2>
            </div>

            <form onSubmit={handleAssignRole} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Target User ID</label>
                <input
                  value={assignUser}
                  onChange={(e) => setAssignUser(e.target.value)}
                  placeholder="e.g. user-12"
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Access Role</label>
                <select
                  value={assignRole}
                  onChange={(e) => setAssignRole(e.target.value)}
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-200"
                >
                  <option value="admin">Administrator (Full Access)</option>
                  <option value="editor">Editor (Governance review allowed)</option>
                  <option value="viewer">Viewer (Read-only)</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={assignRoleMutation.isPending}
                className="w-full btn btn-primary flex justify-center items-center gap-1.5 py-2 text-xs"
              >
                <Key className="h-3.5 w-3.5" /> Apply Access parameters
              </button>
            </form>
          </div>
        </div>
      )}

      {activeTab === 'compliance' && (
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl overflow-hidden">
          <div className="p-4 border-b border-white/[0.06] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ClipboardList className="h-4.5 w-4.5 text-violet-400" />
              <h2 className="text-sm font-semibold text-slate-200">Compliance Audit logs</h2>
            </div>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Audit ID</th>
                <th>Action</th>
                <th>Actor ID</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {loadingAudits ? (
                <tr>
                  <td colSpan={4} className="p-4"><div className="skeleton h-8 w-full" /></td>
                </tr>
              ) : auditLogs.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-center py-16 text-slate-500 text-xs">No compliance audit records found.</td>
                </tr>
              ) : (
                auditLogs.map((log: any, i: number) => (
                  <tr key={i}>
                    <td className="mono text-xs text-slate-400">{log.id || `aud-${i}`}</td>
                    <td className="text-slate-100 font-semibold">{log.action || 'Directory Provision'}</td>
                    <td>{log.actor_id || log.actor || 'demo-user'}</td>
                    <td className="text-xs text-slate-500">{log.timestamp || 'recorded'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
