import React, { useState, useEffect } from 'react';
import { collabApi } from '../api';

export default function CollaborationPage() {
  const [activeTab, setActiveTab] = useState<'threads' | 'decisions' | 'notifications'>('threads');
  const [decisions, setDecisions] = useState<Record<string, unknown>[]>([]);
  const [notifications, setNotifications] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      collabApi.listDecisions(),
      collabApi.listNotifications(),
    ]).then(([d, n]) => {
      if (d.status === 'fulfilled') setDecisions(d.value);
      if (n.status === 'fulfilled') setNotifications(n.value);
      setLoading(false);
    });
  }, []);

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Collaboration</h1>
          <p>Threads, decisions, and team notifications</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'threads' ? ' active' : ''}`} onClick={() => setActiveTab('threads')}>Threads</button>
        <button className={`tab${activeTab === 'decisions' ? ' active' : ''}`} onClick={() => setActiveTab('decisions')}>Decisions</button>
        <button className={`tab${activeTab === 'notifications' ? ' active' : ''}`} onClick={() => setActiveTab('notifications')}>Notifications</button>
      </div>

      {activeTab === 'threads' && (
        <div className="card">
          <div className="card-body">
            <div className="empty-state">
              <div className="empty-state-icon">💬</div>
              <h3>Discussion Threads</h3>
              <p>Create threads on any workspace node to discuss changes, review fixes, and coordinate with your team.</p>
              <button className="btn btn-primary btn-sm" style={{ marginTop: '16px' }}>Create Thread</button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'decisions' && (
        <div className="card">
          <div className="card-body-flush">
            {loading ? (
              <div style={{ padding: '20px' }}>
                <div className="skeleton" style={{ height: '40px', marginBottom: '8px' }} />
              </div>
            ) : decisions.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📋</div>
                <h3>No Decisions</h3>
                <p>Decision logs track important choices made on the platform.</p>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Status</th>
                    <th>Created By</th>
                  </tr>
                </thead>
                <tbody>
                  {decisions.map((d, i) => (
                    <tr key={i}>
                      <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{String(d.title || d.description || 'Decision')}</td>
                      <td><span className="badge badge-success">{String(d.status || 'recorded')}</span></td>
                      <td>{String(d.created_by || d.author || '—')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {activeTab === 'notifications' && (
        <div className="card">
          <div className="card-body-flush">
            {loading ? (
              <div style={{ padding: '20px' }}>
                <div className="skeleton" style={{ height: '40px', marginBottom: '8px' }} />
              </div>
            ) : notifications.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">🔔</div>
                <h3>No Notifications</h3>
                <p>You'll see notifications here when team members mention you or important events occur.</p>
              </div>
            ) : (
              <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {notifications.map((n, i) => (
                  <div key={i} style={{ padding: '12px 16px', background: 'var(--bg-hover)', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span className="status-dot online" />
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-primary)' }}>{String(n.title || n.message || 'Notification')}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{String(n.created_at || n.timestamp || '')}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
