import React, { useState, useEffect } from 'react';
import { analyticsApi } from '../api';

export default function AnalyticsPage() {
  const [alerts, setAlerts] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'alerts' | 'exports'>('overview');

  useEffect(() => {
    analyticsApi.listAlerts()
      .then(setAlerts)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Mock metrics for the overview — these would come from analytics query in production
  const metrics = [
    { label: 'Page Speed Score', value: '92', change: '+3', positive: true },
    { label: 'SEO Health', value: '87%', change: '+5%', positive: true },
    { label: 'Accessibility', value: '94%', change: '+1%', positive: true },
    { label: 'Core Web Vitals', value: '3/3', change: 'Passing', positive: true },
  ];

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Analytics</h1>
          <p>Performance metrics, SEO intelligence, and custom dashboards</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary btn-sm">Export Report</button>
          <button className="btn btn-primary btn-sm">Create Alert</button>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'overview' ? ' active' : ''}`} onClick={() => setActiveTab('overview')}>Overview</button>
        <button className={`tab${activeTab === 'alerts' ? ' active' : ''}`} onClick={() => setActiveTab('alerts')}>Alerts</button>
        <button className={`tab${activeTab === 'exports' ? ' active' : ''}`} onClick={() => setActiveTab('exports')}>Exports</button>
      </div>

      {activeTab === 'overview' && (
        <>
          <div className="stats-grid">
            {metrics.map((m) => (
              <div className="stat-card" key={m.label}>
                <div className="stat-card-label">{m.label}</div>
                <div className="stat-card-value">{m.value}</div>
                <div className={`stat-card-change ${m.positive ? 'positive' : 'negative'}`}>
                  {m.change}
                </div>
              </div>
            ))}
          </div>

          {/* Chart placeholder */}
          <div className="card" style={{ marginTop: '16px' }}>
            <div className="card-header">
              <div className="card-title">Performance Trend</div>
            </div>
            <div className="card-body">
              <div className="chart-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
                <div style={{ textAlign: 'center' }}>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ opacity: 0.3, marginBottom: '12px' }}>
                    <path d="M18 20V10 M12 20V4 M6 20v-6" />
                  </svg>
                  <p style={{ fontSize: '13px' }}>Charts render with live metric data from the analytics engine.</p>
                  <p style={{ fontSize: '12px', marginTop: '4px', opacity: 0.6 }}>Query the /v1/analytics/query endpoint to populate.</p>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === 'alerts' && (
        <div className="card">
          <div className="card-body-flush">
            {loading ? (
              <div style={{ padding: '20px' }}>
                <div className="skeleton" style={{ height: '40px', marginBottom: '8px' }} />
                <div className="skeleton" style={{ height: '40px', marginBottom: '8px' }} />
              </div>
            ) : alerts.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">🔔</div>
                <h3>No Alerts Configured</h3>
                <p>Create alert rules to get notified when metrics cross thresholds.</p>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Metric</th>
                    <th>Condition</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((a, i) => (
                    <tr key={i}>
                      <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{String(a.name || a.rule_name || 'Alert')}</td>
                      <td className="mono">{String(a.metric_name || a.metric || '—')}</td>
                      <td>{String(a.operator || '>')} {String(a.threshold || '—')}</td>
                      <td><span className="badge badge-success">Active</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {activeTab === 'exports' && (
        <div className="card">
          <div className="card-body">
            <div className="empty-state">
              <div className="empty-state-icon">📊</div>
              <h3>Export Reports</h3>
              <p>Generate PDF, CSV, or JSON reports from your analytics data.</p>
              <button className="btn btn-primary btn-sm" style={{ marginTop: '16px' }}>Generate Report</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
