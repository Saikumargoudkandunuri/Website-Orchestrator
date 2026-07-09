import React, { useState, useEffect } from 'react';
import { enterpriseApi } from '../api';

export default function EnterprisePage() {
  const [activeTab, setActiveTab] = useState<'org' | 'billing' | 'roles' | 'audit'>('org');
  const [usage, setUsage] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    enterpriseApi.getUsage()
      .then(setUsage)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Enterprise</h1>
          <p>Organization management, billing, roles, and compliance</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'org' ? ' active' : ''}`} onClick={() => setActiveTab('org')}>Organization</button>
        <button className={`tab${activeTab === 'billing' ? ' active' : ''}`} onClick={() => setActiveTab('billing')}>Billing & Usage</button>
        <button className={`tab${activeTab === 'roles' ? ' active' : ''}`} onClick={() => setActiveTab('roles')}>Roles & Access</button>
        <button className={`tab${activeTab === 'audit' ? ' active' : ''}`} onClick={() => setActiveTab('audit')}>Audit Logs</button>
      </div>

      {activeTab === 'org' && (
        <div className="card" style={{ maxWidth: '540px' }}>
          <div className="card-header">
            <div className="card-title">Create Organization</div>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Organization Name</label>
                <input className="input" placeholder="Acme Corp" />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Slug</label>
                <input className="input" placeholder="acme-corp" />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Plan</label>
                <select className="input" style={{ appearance: 'auto' }}>
                  <option value="starter">Starter</option>
                  <option value="professional">Professional</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </div>
              <button className="btn btn-primary btn-sm" style={{ alignSelf: 'flex-start' }}>Create Organization</button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'billing' && (
        <>
          <div className="stats-grid">
            {Object.entries(usage).length === 0 && !loading ? (
              <div className="stat-card">
                <div className="stat-card-label">Status</div>
                <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>No Usage Data</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>Create a subscription to start tracking usage.</div>
              </div>
            ) : (
              Object.entries(usage).map(([key, val]) => (
                <div className="stat-card" key={key}>
                  <div className="stat-card-label">{key.replace(/_/g, ' ')}</div>
                  <div className="stat-card-value">{val.toLocaleString()}</div>
                </div>
              ))
            )}
          </div>

          <div className="card" style={{ marginTop: '16px', maxWidth: '540px' }}>
            <div className="card-header">
              <div className="card-title">Create Subscription</div>
            </div>
            <div className="card-body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <select className="input" style={{ appearance: 'auto' }}>
                  <option value="monthly">Monthly Billing</option>
                  <option value="annual">Annual Billing (Save 20%)</option>
                </select>
                <button className="btn btn-primary btn-sm" style={{ alignSelf: 'flex-start' }}>Subscribe</button>
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === 'roles' && (
        <div className="card" style={{ maxWidth: '540px' }}>
          <div className="card-header">
            <div className="card-title">Assign Role</div>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <input className="input" placeholder="User ID" />
              <select className="input" style={{ appearance: 'auto' }}>
                <option value="admin">Admin</option>
                <option value="editor">Editor</option>
                <option value="viewer">Viewer</option>
              </select>
              <button className="btn btn-primary btn-sm" style={{ alignSelf: 'flex-start' }}>Assign Role</button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'audit' && (
        <div className="card">
          <div className="card-body">
            <div className="empty-state">
              <div className="empty-state-icon">🔍</div>
              <h3>Enterprise Audit Logs</h3>
              <p>Create an organization to start viewing enterprise-level audit logs with SCIM integration.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
