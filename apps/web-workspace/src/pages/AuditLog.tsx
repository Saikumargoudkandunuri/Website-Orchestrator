import React, { useState, useEffect } from 'react';
import { coreApi, type AuditEntry } from '../api';

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    coreApi.listAuditLog()
      .then(setEntries)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Audit Trail</h1>
          <p>Complete history of all platform actions and governance decisions</p>
        </div>
        <div className="page-header-actions">
          <span className="badge badge-default">{entries.length} events</span>
        </div>
      </div>

      <div className="card">
        <div className="card-body-flush">
          {loading ? (
            <div style={{ padding: '20px' }}>
              {[1, 2, 3, 4, 5].map((n) => (
                <div key={n} className="skeleton" style={{ height: '40px', marginBottom: '8px' }} />
              ))}
            </div>
          ) : entries.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <h3>No Audit Entries</h3>
              <p>Actions will be recorded here as you use the platform.</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Action</th>
                  <th>Actor</th>
                  <th>Detail</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="mono" style={{ whiteSpace: 'nowrap' }}>{entry.timestamp}</td>
                    <td>
                      <span className={`badge badge-${entry.action.includes('approve') ? 'success' : entry.action.includes('reject') ? 'error' : entry.action.includes('crawl') ? 'info' : 'default'}`}>
                        {entry.action}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{entry.actor}</td>
                    <td>{entry.detail}</td>
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
