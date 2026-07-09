import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { enterpriseApi } from '../api';
import { Building, ShieldCheck, UserCheck, Key, Plus, ClipboardList } from 'lucide-react';
import { GlassCard, AnimatedButton, GlassInput, StatusBadge } from '../components/PremiumUI';
import { motion } from 'framer-motion';

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
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-8"
    >
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Enterprise Administration</h1>
          <p className="text-sm text-slate-500 mt-1">Manage directory synchronization parameters, corporative organizations, and SSO rules</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'orgs' ? ' active' : ''}`} onClick={() => setActiveTab('orgs')}>Organizations</button>
        <button className={`tab${activeTab === 'users' ? ' active' : ''}`} onClick={() => setActiveTab('users')}>Directory Sync (SCIM)</button>
        <button className={`tab${activeTab === 'roles' ? ' active' : ''}`} onClick={() => setActiveTab('roles')}>Access Roles</button>
        <button className={`tab${activeTab === 'compliance' ? ' active' : ''}`} onClick={() => setActiveTab('compliance')}>Compliance Audit</button>
      </div>

      {activeTab === 'orgs' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Create org */}
          <GlassCard className="space-y-4 xl:col-span-1">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Building className="h-4.5 w-4.5 text-indigo-500" />
              <h2 className="text-sm font-bold text-slate-800">Create Corporate Org</h2>
            </div>
            
            <form onSubmit={handleCreateOrg} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Organization Name</label>
                <GlassInput
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="e.g. Acme Corporation"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Workspace Slug</label>
                <GlassInput
                  value={orgSlug}
                  onChange={(e) => setOrgSlug(e.target.value)}
                  placeholder="acme-corp"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Corporate Tier</label>
                <select
                  value={orgPlan}
                  onChange={(e) => setOrgPlan(e.target.value)}
                  className="w-full bg-white/70 border border-slate-200 text-slate-700 text-xs px-3 py-2.5 rounded-xl focus:outline-none"
                >
                  <option value="business">Business Pro</option>
                  <option value="enterprise">Corporate Enterprise</option>
                </select>
              </div>

              <AnimatedButton
                type="submit"
                disabled={createOrgMutation.isPending}
                variant="primary"
                className="w-full py-2.5"
              >
                <Plus className="h-4 w-4" /> Save Organization
              </AnimatedButton>
            </form>
          </GlassCard>

          {/* Org details preview */}
          <GlassCard className="xl:col-span-2 p-5 space-y-3">
            <h2 className="text-sm font-bold text-slate-800">Enterprise Tenant Details</h2>
            <div className="bg-slate-950 border border-slate-900 p-4 rounded-xl font-mono text-[11px] text-slate-400 space-y-2 shadow-inner">
              <div>Tenant Scope ID: <span className="text-slate-300">demo-tenant</span></div>
              <div>SSO Federation: <span className="text-slate-500">Not configured (SAML/OIDC available)</span></div>
              <div>Active Workspaces: <span className="text-slate-300">3 Workspaces</span></div>
            </div>
          </GlassCard>
        </div>
      )}

      {activeTab === 'users' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Create user SCIM */}
          <GlassCard className="space-y-4 xl:col-span-1">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <UserCheck className="h-4.5 w-4.5 text-indigo-500" />
              <h2 className="text-sm font-bold text-slate-800">Provision Directory User</h2>
            </div>

            <form onSubmit={handleCreateScimUser} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Username</label>
                <GlassInput
                  value={scimUsername}
                  onChange={(e) => setScimUsername(e.target.value)}
                  placeholder="e.g. alice.smith"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Primary Email</label>
                <GlassInput
                  type="email"
                  value={scimEmail}
                  onChange={(e) => setScimEmail(e.target.value)}
                  placeholder="alice@acme.com"
                />
              </div>

              <AnimatedButton
                type="submit"
                disabled={createScimUserMutation.isPending}
                variant="primary"
                className="w-full py-2.5"
              >
                <Plus className="h-4 w-4" /> Provision Directory User
              </AnimatedButton>
            </form>
          </GlassCard>

          <GlassCard className="xl:col-span-2 p-5 space-y-3">
            <h2 className="text-sm font-bold text-slate-800">SCIM Directory Status</h2>
            <div className="bg-slate-950 border border-slate-900 p-4 rounded-xl font-mono text-[11px] text-slate-400 space-y-2 shadow-inner">
              <div>Sync Engine Status: <span className="text-emerald-400 font-bold">Active Connection</span></div>
              <div>SCIM Endpoint URL: <span className="text-slate-300">/v1/enterprise/scim/v2/Users</span></div>
            </div>
          </GlassCard>
        </div>
      )}

      {activeTab === 'roles' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          <GlassCard className="space-y-4 xl:col-span-1">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <ShieldCheck className="h-4.5 w-4.5 text-indigo-500" />
              <h2 className="text-sm font-bold text-slate-800">Assign Member Access</h2>
            </div>

            <form onSubmit={handleAssignRole} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Target User ID</label>
                <GlassInput
                  value={assignUser}
                  onChange={(e) => setAssignUser(e.target.value)}
                  placeholder="e.g. user-12"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Access Role</label>
                <select
                  value={assignRole}
                  onChange={(e) => setAssignRole(e.target.value)}
                  className="w-full bg-white/70 border border-slate-200 text-slate-700 text-xs px-3 py-2.5 rounded-xl focus:outline-none"
                >
                  <option value="admin">Administrator (Full Access)</option>
                  <option value="editor">Editor (Governance review allowed)</option>
                  <option value="viewer">Viewer (Read-only)</option>
                </select>
              </div>

              <AnimatedButton
                type="submit"
                disabled={assignRoleMutation.isPending}
                variant="primary"
                className="w-full py-2.5"
              >
                <Key className="h-3.5 w-3.5" /> Apply Access parameters
              </AnimatedButton>
            </form>
          </GlassCard>
        </div>
      )}

      {activeTab === 'compliance' && (
        <GlassCard className="p-0 overflow-hidden">
          <div className="p-5 border-b border-slate-100 bg-white/50">
            <div className="flex items-center gap-2">
              <ClipboardList className="h-4.5 w-4.5 text-indigo-500" />
              <h2 className="text-sm font-bold text-slate-800">Compliance Audit logs</h2>
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
                  <td colSpan={4} className="text-center py-16 text-slate-400 text-xs">No compliance audit records found.</td>
                </tr>
              ) : (
                auditLogs.map((log: any, i: number) => (
                  <tr key={i}>
                    <td className="mono text-xs text-slate-400">{log.id || `aud-${i}`}</td>
                    <td className="text-slate-900 font-bold">{log.action || 'Directory Sync Provision'}</td>
                    <td className="font-semibold text-slate-700">{log.actor_id || log.actor || 'demo-user'}</td>
                    <td className="text-xs text-slate-400">{log.timestamp || 'recorded'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </GlassCard>
      )}
    </motion.div>
  );
}
