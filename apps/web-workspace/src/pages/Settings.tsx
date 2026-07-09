import React, { useState } from 'react';
import { Settings, Shield, User, Bell, Sliders, Key, Globe, Terminal } from 'lucide-react';

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'general' | 'branding' | 'sso' | 'scim'>('general');

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">System Settings</h1>
          <p className="text-sm text-slate-400">Configure workspace parameters, verify SSO integrations, and customize dashboard branding</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'general' ? ' active' : ''}`} onClick={() => setActiveTab('general')}>General</button>
        <button className={`tab${activeTab === 'branding' ? ' active' : ''}`} onClick={() => setActiveTab('branding')}>Branding</button>
        <button className={`tab${activeTab === 'sso' ? ' active' : ''}`} onClick={() => setActiveTab('sso')}>SSO (SAML)</button>
        <button className={`tab${activeTab === 'scim' ? ' active' : ''}`} onClick={() => setActiveTab('scim')}>SCIM Integration</button>
      </div>

      {activeTab === 'general' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold text-slate-200">Workspace Configurations</h2>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">Tenant ID</label>
                <input className="input mono text-xs" defaultValue="demo-tenant" readOnly style={{ opacity: 0.7 }} />
              </div>
              <div>
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">Global Crawler Timeout (seconds)</label>
                <input type="number" className="input text-xs" defaultValue={30} />
              </div>
            </div>
          </div>

          <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold text-slate-200">API Connection</h2>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">Backend Base URL</label>
                <input className="input mono text-xs" defaultValue="http://127.0.0.1:8000" readOnly style={{ opacity: 0.7 }} />
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <span className="text-xs text-slate-300">Connected to FastAPI server</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'branding' && (
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 max-w-xl">
          <h2 className="text-sm font-semibold text-slate-200">Dashboard Theme & Styling</h2>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">Workspace Title Name</label>
              <input className="input text-xs" defaultValue="Website Orchestrator" />
            </div>
            <div>
              <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">Accent Theme Hue</label>
              <select className="input text-xs" style={{ appearance: 'auto' }}>
                <option value="violet">Corporate Violet</option>
                <option value="emerald">Forest Emerald</option>
                <option value="sky">Deep Sea Sky</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'sso' && (
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 max-w-xl">
          <h2 className="text-sm font-semibold text-slate-200">Single Sign-On (SAML / OIDC)</h2>
          <p className="text-xs text-slate-400">Delegate user identity management to corporate identity providers like Okta or Azure AD.</p>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">Metadata Entry URL</label>
              <input className="input text-xs" placeholder="https://okta.com/acme/saml/metadata" />
            </div>
            <button className="btn btn-primary btn-sm">Configure SSO Endpoint</button>
          </div>
        </div>
      )}

      {activeTab === 'scim' && (
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 max-w-xl">
          <h2 className="text-sm font-semibold text-slate-200">Directory Provisioning (SCIM 2.0)</h2>
          <p className="text-xs text-slate-400">Sync workspace memberships automatically when directory users are modified.</p>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">Secret Token</label>
              <input className="input mono text-xs" defaultValue="scim_prov_token_showcase_key_1052" readOnly />
            </div>
            <div className="text-[11px] text-slate-400">
              Pass this token in authorization headers to perform sync operations on: <span className="font-mono bg-slate-950 px-1 rounded text-slate-300">/v1/enterprise/scim/v2/Users</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
