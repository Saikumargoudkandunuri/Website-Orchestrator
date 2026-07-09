import React, { useState, useEffect } from 'react';
import { coreApi, analyticsApi, type Issue, type SuggestedFix, type AuditEntry } from '../api';

export default function DashboardPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [fixes, setFixes] = useState<SuggestedFix[]>([]);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      coreApi.listIssues(),
      coreApi.listFixes(),
      coreApi.listAuditLog(),
    ]).then(([issR, fixR, audR]) => {
      if (issR.status === 'fulfilled') setIssues(issR.value);
      if (fixR.status === 'fulfilled') setFixes(fixR.value);
      if (audR.status === 'fulfilled') setAuditLog(audR.value);
      setLoading(false);
    });
  }, []);

  const criticalIssues = issues.filter((i) => i.severity === 'critical' || i.severity === 'high');
  const pendingFixes = fixes.filter((f) => f.status === 'pending');
  const approvedFixes = fixes.filter((f) => f.status === 'approved');

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Dashboard</h1>
          <p>Platform overview and real-time intelligence</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary btn-sm">Export Report</button>
          <button className="btn btn-primary btn-sm">New Crawl</button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-card-label">Total Issues</div>
          <div className="stat-card-value">{loading ? '—' : issues.length}</div>
          <div className={`stat-card-change ${criticalIssues.length > 0 ? 'negative' : 'positive'}`}>
            {criticalIssues.length} critical
          </div>
          <div className="stat-card-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-label">Suggested Fixes</div>
          <div className="stat-card-value">{loading ? '—' : fixes.length}</div>
          <div className="stat-card-change positive">
            {approvedFixes.length} approved
          </div>
          <div className="stat-card-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-label">Pending Review</div>
          <div className="stat-card-value">{loading ? '—' : pendingFixes.length}</div>
          <div className="stat-card-change positive">
            {pendingFixes.length === 0 ? 'All clear' : 'Needs attention'}
          </div>
          <div className="stat-card-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M12 6v6l4 2"/></svg>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-card-label">Audit Events</div>
          <div className="stat-card-value">{loading ? '—' : auditLog.length}</div>
          <div className="stat-card-change positive">Tracked</div>
          <div className="stat-card-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
          </div>
        </div>
      </div>

      {/* Two Column Layout */}
      <div className="grid-2">
        {/* Recent Issues */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Recent Issues</div>
              <div className="card-subtitle">Latest detected problems</div>
            </div>
            <button className="btn btn-ghost btn-sm">View All →</button>
          </div>
          <div className="card-body-flush">
            {loading ? (
              <div style={{ padding: '20px' }}>
                <div className="skeleton" style={{ height: '16px', marginBottom: '12px', width: '80%' }} />
                <div className="skeleton" style={{ height: '16px', marginBottom: '12px', width: '60%' }} />
                <div className="skeleton" style={{ height: '16px', width: '70%' }} />
              </div>
            ) : issues.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">✓</div>
                <h3>No Issues Found</h3>
                <p>Run a crawl to start detecting issues.</p>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Category</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {issues.slice(0, 5).map((issue) => (
                    <tr key={issue.id}>
                      <td>
                        <span className={`badge badge-${issue.severity === 'critical' || issue.severity === 'high' ? 'error' : issue.severity === 'medium' ? 'warning' : 'info'}`}>
                          {issue.severity}
                        </span>
                      </td>
                      <td style={{ color: 'var(--text-primary)' }}>{issue.category}</td>
                      <td>{issue.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Audit Trail */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Activity Timeline</div>
              <div className="card-subtitle">Recent platform events</div>
            </div>
            <button className="btn btn-ghost btn-sm">View All →</button>
          </div>
          <div className="card-body">
            {loading ? (
              <div>
                <div className="skeleton" style={{ height: '16px', marginBottom: '12px', width: '90%' }} />
                <div className="skeleton" style={{ height: '16px', marginBottom: '12px', width: '75%' }} />
                <div className="skeleton" style={{ height: '16px', width: '85%' }} />
              </div>
            ) : auditLog.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📋</div>
                <h3>No Activity Yet</h3>
                <p>Platform events will appear here.</p>
              </div>
            ) : (
              <div className="timeline">
                {auditLog.slice(0, 6).map((entry) => (
                  <div key={entry.id} className="timeline-item">
                    <div className={`timeline-dot ${entry.action.includes('approve') ? 'success' : entry.action.includes('reject') ? 'error' : ''}`} />
                    <div className="timeline-content">
                      <div className="timeline-title">{entry.action}</div>
                      <div className="timeline-time">{entry.actor} · {entry.timestamp}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
