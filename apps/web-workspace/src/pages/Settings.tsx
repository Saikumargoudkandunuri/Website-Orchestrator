import React from 'react';

export default function SettingsPage() {
  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Settings</h1>
          <p>Platform configuration and preferences</p>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div className="card-title">General</div>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Platform Name</label>
                <input className="input" defaultValue="Website Orchestrator" />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Tenant ID</label>
                <input className="input mono" defaultValue="demo-tenant" readOnly style={{ opacity: 0.7 }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Theme</label>
                <select className="input" style={{ appearance: 'auto' }}>
                  <option value="dark">Dark</option>
                  <option value="light">Light</option>
                  <option value="system">System</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">API Configuration</div>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>API Base URL</label>
                <input className="input mono" defaultValue="http://127.0.0.1:8000" readOnly style={{ opacity: 0.7 }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Backend Status</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="status-dot online" />
                  <span style={{ fontSize: '13px', color: 'var(--success)' }}>Connected</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Keyboard Shortcuts</div>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {[
                { keys: '⌘K', action: 'Open Command Palette' },
                { keys: '⌘J', action: 'Toggle AI Copilot' },
                { keys: 'Esc', action: 'Close Modal / Panel' },
              ].map((shortcut) => (
                <div key={shortcut.keys} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{shortcut.action}</span>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', padding: '2px 8px', borderRadius: '4px' }}>{shortcut.keys}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Platform Info</div>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {[
                { label: 'Version', value: '1.0.0' },
                { label: 'Architecture', value: 'Milestones 1–7 + SaaS Platform' },
                { label: 'Frontend', value: 'React 18 + TypeScript + Vite' },
                { label: 'Backend', value: 'FastAPI + Python 3.12' },
                { label: 'AI Engine', value: 'Agentic Memory + Reflection + Missions' },
              ].map((info) => (
                <div key={info.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-tertiary)' }}>{info.label}</span>
                  <span style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: 500 }}>{info.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
