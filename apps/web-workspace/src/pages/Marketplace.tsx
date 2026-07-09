import React, { useState, useEffect } from 'react';
import { marketplaceApi } from '../api';

export default function MarketplacePage() {
  const [apps, setApps] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    marketplaceApi.listApps()
      .then(setApps)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const categories = [
    { name: 'SEO Tools', count: 12, icon: '🔍' },
    { name: 'Analytics', count: 8, icon: '📊' },
    { name: 'Content', count: 15, icon: '📝' },
    { name: 'Performance', count: 6, icon: '⚡' },
    { name: 'Security', count: 4, icon: '🔒' },
    { name: 'Integrations', count: 20, icon: '🔗' },
  ];

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Marketplace</h1>
          <p>Discover and install apps, plugins, and integrations</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary btn-sm">Register App</button>
        </div>
      </div>

      {/* Categories */}
      <div className="stats-grid" style={{ marginBottom: '24px' }}>
        {categories.map((cat) => (
          <div className="stat-card" key={cat.name} style={{ cursor: 'pointer', textAlign: 'center' }}>
            <div style={{ fontSize: '28px', marginBottom: '8px' }}>{cat.icon}</div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>{cat.name}</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>{cat.count} apps</div>
          </div>
        ))}
      </div>

      {/* Apps List */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Available Apps</div>
          <span className="badge badge-default">{apps.length} apps</span>
        </div>
        <div className="card-body-flush">
          {loading ? (
            <div style={{ padding: '20px' }}>
              {[1, 2, 3].map((n) => (
                <div key={n} className="skeleton" style={{ height: '60px', marginBottom: '8px' }} />
              ))}
            </div>
          ) : apps.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🏪</div>
              <h3>Marketplace Coming to Life</h3>
              <p>Register developer apps via the API to populate the marketplace.</p>
            </div>
          ) : (
            <div style={{ padding: '16px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
              {apps.map((app, i) => (
                <div key={i} style={{ padding: '16px', background: 'var(--bg-hover)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>{String(app.name || app.app_name || `App ${i + 1}`)}</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>{String(app.description || '—')}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
                    <span className="badge badge-success">{String(app.status || 'available')}</span>
                    <button className="btn btn-primary btn-sm">Install</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
