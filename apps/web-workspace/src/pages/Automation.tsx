import React, { useState } from 'react';
import { automationApi } from '../api';

export default function AutomationPage() {
  const [activeTab, setActiveTab] = useState<'workflows' | 'executions'>('workflows');
  const [creating, setCreating] = useState(false);
  const [workflowName, setWorkflowName] = useState('');
  const [workflowDesc, setWorkflowDesc] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const handleCreate = async () => {
    if (!workflowName.trim()) return;
    setCreating(true);
    try {
      const wf = await automationApi.createWorkflow({
        name: workflowName,
        description: workflowDesc,
        trigger_type: 'manual',
        steps: [{ action: 'crawl', params: {} }],
      });
      setResult(wf);
      setWorkflowName('');
      setWorkflowDesc('');
    } catch {
      /* handled gracefully */
    } finally {
      setCreating(false);
    }
  };

  const templateWorkflows = [
    { name: 'Weekly SEO Audit', description: 'Automatically crawl and generate reports every week', trigger: 'scheduled', icon: '📅' },
    { name: 'Issue Auto-Fix', description: 'Detect issues and apply safe fixes automatically', trigger: 'event', icon: '⚡' },
    { name: 'Performance Monitor', description: 'Track Core Web Vitals and alert on regressions', trigger: 'cron', icon: '📊' },
    { name: 'Content Freshness', description: 'Check for stale content and notify content team', trigger: 'scheduled', icon: '📝' },
  ];

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Automation Studio</h1>
          <p>Create and manage automated workflows for website operations</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'workflows' ? ' active' : ''}`} onClick={() => setActiveTab('workflows')}>Workflows</button>
        <button className={`tab${activeTab === 'executions' ? ' active' : ''}`} onClick={() => setActiveTab('executions')}>Executions</button>
      </div>

      {activeTab === 'workflows' && (
        <>
          {/* Templates */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>Templates</h3>
            <div className="stats-grid">
              {templateWorkflows.map((t) => (
                <div className="stat-card" key={t.name} style={{ cursor: 'pointer' }}>
                  <div style={{ fontSize: '24px', marginBottom: '8px' }}>{t.icon}</div>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>{t.name}</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>{t.description}</div>
                  <span className="badge badge-default" style={{ marginTop: '8px' }}>{t.trigger}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Create Custom */}
          <div className="card" style={{ maxWidth: '540px' }}>
            <div className="card-header">
              <div className="card-title">Create Custom Workflow</div>
            </div>
            <div className="card-body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <input className="input" placeholder="Workflow name" value={workflowName} onChange={(e) => setWorkflowName(e.target.value)} />
                <input className="input" placeholder="Description (optional)" value={workflowDesc} onChange={(e) => setWorkflowDesc(e.target.value)} />
                <button className="btn btn-primary btn-sm" onClick={handleCreate} disabled={creating} style={{ alignSelf: 'flex-start' }}>
                  {creating ? 'Creating…' : 'Create Workflow'}
                </button>
                {result && (
                  <div style={{ padding: '10px', background: 'var(--success-bg)', borderRadius: 'var(--radius-md)', color: 'var(--success)', fontSize: '12px' }}>
                    ✓ Workflow created: {String(result.id || result.name)}
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === 'executions' && (
        <div className="card">
          <div className="card-body">
            <div className="empty-state">
              <div className="empty-state-icon">⚙️</div>
              <h3>No Executions Yet</h3>
              <p>Create and run a workflow to see execution traces here.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
