import React, { useState } from 'react';
import { GlassCard, AnimatedButton, GlassInput } from '../components/PremiumUI';
import { motion } from 'framer-motion';

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'general' | 'branding' | 'sso' | 'scim'>('general');

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-8"
    >
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">System Settings</h1>
          <p className="text-sm text-slate-500 mt-1">Configure workspace parameters, verify SSO integrations, and customize dashboard branding</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'general' ? ' active' : ''}`} onClick={() => setActiveTab('general')}>General</button>
        <button className={`tab${activeTab === 'branding' ? ' active' : ''}`} onClick={() => setActiveTab('branding')}>Branding</button>
        <button className={`tab${activeTab === 'sso' ? ' active' : ''}`} onClick={() => setActiveTab('sso')}>SSO (SAML)</button>
        <button className={`tab${activeTab === 'scim' ? ' active' : ''}`} onClick={() => setActiveTab('scim')}>SCIM Integration</button>
      </div>

      {activeTab === 'general' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <GlassCard className="space-y-4">
            <h2 className="text-sm font-bold text-slate-800">Workspace Configurations</h2>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Tenant ID</label>
                <GlassInput defaultValue="demo-tenant" readOnly style={{ opacity: 0.7 }} />
              </div>
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Global Crawler Timeout (seconds)</label>
                <GlassInput type="number" defaultValue={30} />
              </div>
            </div>
          </GlassCard>

          <GlassCard className="space-y-4">
            <h2 className="text-sm font-bold text-slate-800">API Connection</h2>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Backend Base URL</label>
                <GlassInput defaultValue="http://127.0.0.1:8000" readOnly style={{ opacity: 0.7 }} />
              </div>
              <div className="flex items-center gap-2 mt-3">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-xs font-semibold text-slate-600">Connected to FastAPI server</span>
              </div>
            </div>
          </GlassCard>
        </div>
      )}

      {activeTab === 'branding' && (
        <GlassCard className="space-y-4 max-w-xl">
          <h2 className="text-sm font-bold text-slate-800">Dashboard Theme & Styling</h2>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Workspace Title Name</label>
              <GlassInput defaultValue="Website Orchestrator" />
            </div>
            <div>
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Accent Theme Hue</label>
              <select className="w-full bg-white/70 border border-slate-200 text-slate-700 text-xs px-3 py-2.5 rounded-xl focus:outline-none focus:border-indigo-500">
                <option value="violet">Corporate Violet</option>
                <option value="emerald">Forest Emerald</option>
                <option value="sky">Deep Sea Sky</option>
              </select>
            </div>
          </div>
        </GlassCard>
      )}

      {activeTab === 'sso' && (
        <GlassCard className="space-y-4 max-w-xl">
          <h2 className="text-sm font-bold text-slate-800">Single Sign-On (SAML / OIDC)</h2>
          <p className="text-xs text-slate-400 leading-relaxed">Delegate user identity management to corporate identity providers like Okta or Azure AD.</p>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Metadata Entry URL</label>
              <GlassInput placeholder="https://okta.com/acme/saml/metadata" />
            </div>
            <AnimatedButton variant="primary" className="py-2">Configure SSO Endpoint</AnimatedButton>
          </div>
        </GlassCard>
      )}

      {activeTab === 'scim' && (
        <GlassCard className="space-y-4 max-w-xl">
          <h2 className="text-sm font-bold text-slate-800">Directory Provisioning (SCIM 2.0)</h2>
          <p className="text-xs text-slate-400 leading-relaxed">Sync workspace memberships automatically when directory users are modified.</p>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Secret Token</label>
              <GlassInput defaultValue="scim_prov_token_showcase_key_1052" readOnly />
            </div>
            <div className="text-[11px] text-slate-400 font-semibold leading-relaxed">
              Pass this token in authorization headers to sync directory entries on: <span className="font-mono bg-slate-950 px-1.5 py-0.5 rounded text-slate-300">/v1/enterprise/scim/v2/Users</span>
            </div>
          </div>
        </GlassCard>
      )}
    </motion.div>
  );
}
