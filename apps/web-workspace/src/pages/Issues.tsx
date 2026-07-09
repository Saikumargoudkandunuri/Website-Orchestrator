import React, { useState, useEffect } from 'react';
import { coreApi, type Issue } from '../api';

export default function IssuesPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    coreApi.listIssues()
      .then(setIssues)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter === 'all' ? issues : issues.filter((i) => i.severity === filter);
  const severities = ['all', ...new Set(issues.map((i) => i.severity))];

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Issues</h1>
          <p>Detected problems across your website</p>
        </div>
        <div className="page-header-actions">
          <span className="badge badge-default">{issues.length} total</span>
        </div>
      </div>

      {/* Filters */}
      <div className="tabs">
        {severities.map((s) => (
          <button key={s} className={`tab${filter === s ? ' active' : ''}`} onClick={() => setFilter(s)}>
            {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
            <span style={{ marginLeft: '6px', opacity: 0.5 }}>
              {s === 'all' ? issues.length : issues.filter((i) => i.severity === s).length}
            </span>
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-body-flush">
          {loading ? (
            <div style={{ padding: '20px' }}>
              {[1, 2, 3, 4, 5].map((n) => (
                <div key={n} className="skeleton" style={{ height: '40px', marginBottom: '8px' }} />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🔍</div>
              <h3>No Issues Found</h3>
              <p>Run a crawl to detect issues, or adjust your filters.</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Category</th>
                  <th>URL</th>
                  <th>Description</th>
                  <th>Detected</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((issue) => (
                  <tr key={issue.id}>
                    <td>
                      <span className={`badge badge-${issue.severity === 'critical' || issue.severity === 'high' ? 'error' : issue.severity === 'medium' ? 'warning' : 'info'}`}>
                        {issue.severity}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{issue.category}</td>
                    <td className="mono" style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{issue.url}</td>
                    <td>{issue.description}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{issue.detected_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
