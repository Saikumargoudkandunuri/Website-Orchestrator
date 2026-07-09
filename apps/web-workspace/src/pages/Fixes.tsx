import React, { useState, useEffect } from 'react';
import { coreApi, type SuggestedFix } from '../api';

export default function FixesPage() {
  const [fixes, setFixes] = useState<SuggestedFix[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadFixes = () => {
    setLoading(true);
    coreApi.listFixes()
      .then(setFixes)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadFixes(); }, []);

  const handleAction = async (id: string, action: 'approve' | 'reject' | 'rollback') => {
    setActionLoading(id);
    try {
      if (action === 'approve') await coreApi.approveFix(id, 'Approved from console');
      else if (action === 'reject') await coreApi.rejectFix(id, 'Rejected from console');
      else await coreApi.rollbackFix(id, 'Rolled back from console');
      loadFixes();
    } catch {
      /* handled gracefully */
    } finally {
      setActionLoading(null);
    }
  };

  const filtered = filter === 'all' ? fixes : fixes.filter((f) => f.status === filter);
  const statuses = ['all', ...new Set(fixes.map((f) => f.status))];

  const statusBadge = (status: string) => {
    if (status === 'approved' || status === 'applied') return 'success';
    if (status === 'rejected') return 'error';
    if (status === 'pending') return 'warning';
    return 'default';
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Fixes</h1>
          <p>AI-generated fixes for detected issues — review, approve, or reject</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary btn-sm" onClick={loadFixes}>Refresh</button>
        </div>
      </div>

      <div className="tabs">
        {statuses.map((s) => (
          <button key={s} className={`tab${filter === s ? ' active' : ''}`} onClick={() => setFilter(s)}>
            {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-body-flush">
          {loading ? (
            <div style={{ padding: '20px' }}>
              {[1, 2, 3].map((n) => (
                <div key={n} className="skeleton" style={{ height: '60px', marginBottom: '8px' }} />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🔧</div>
              <h3>No Fixes Available</h3>
              <p>Run a crawl to generate AI-powered fix suggestions.</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Description</th>
                  <th>Issue ID</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((fix) => (
                  <tr key={fix.id}>
                    <td><span className={`badge badge-${statusBadge(fix.status)}`}>{fix.status}</span></td>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500, maxWidth: '300px' }}>{fix.description}</td>
                    <td className="mono">{fix.issue_id}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        {fix.status === 'pending' && (
                          <>
                            <button
                              className="btn btn-sm"
                              style={{ background: 'var(--success-bg)', color: 'var(--success)', border: '1px solid rgba(34,197,94,0.3)' }}
                              onClick={() => handleAction(fix.id, 'approve')}
                              disabled={actionLoading === fix.id}
                            >
                              Approve
                            </button>
                            <button
                              className="btn btn-sm"
                              style={{ background: 'var(--error-bg)', color: 'var(--error)', border: '1px solid rgba(239,68,68,0.3)' }}
                              onClick={() => handleAction(fix.id, 'reject')}
                              disabled={actionLoading === fix.id}
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {(fix.status === 'approved' || fix.status === 'applied') && (
                          <button
                            className="btn btn-sm btn-secondary"
                            onClick={() => handleAction(fix.id, 'rollback')}
                            disabled={actionLoading === fix.id}
                          >
                            Rollback
                          </button>
                        )}
                      </div>
                    </td>
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
