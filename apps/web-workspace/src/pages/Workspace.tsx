import React, { useState, useEffect } from 'react';
import { workspaceApi, type Workspace } from '../api';

export default function WorkspacePage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedWs, setSelectedWs] = useState<Workspace | null>(null);

  useEffect(() => {
    workspaceApi.list()
      .then((ws) => { setWorkspaces(ws); if (ws.length > 0) setSelectedWs(ws[0]); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Workspace</h1>
          <p>AI-powered collaborative canvas for website operations</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary btn-sm">Search Commands</button>
        </div>
      </div>

      {loading ? (
        <div className="stats-grid">
          {[1, 2, 3].map((n) => (
            <div key={n} className="skeleton" style={{ height: '120px' }} />
          ))}
        </div>
      ) : workspaces.length === 0 ? (
        <div className="card">
          <div className="card-body">
            <div className="empty-state">
              <div className="empty-state-icon">🎨</div>
              <h3>No Workspaces</h3>
              <p>Workspaces are created via the API. Each workspace contains canvases with draggable nodes representing your website operations.</p>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Workspace Selector */}
          <div className="stats-grid">
            {workspaces.map((ws) => (
              <div
                key={ws.id}
                className="stat-card"
                style={{
                  cursor: 'pointer',
                  borderColor: selectedWs?.id === ws.id ? 'var(--accent-primary)' : undefined,
                  boxShadow: selectedWs?.id === ws.id ? 'var(--shadow-glow)' : undefined,
                }}
                onClick={() => setSelectedWs(ws)}
              >
                <div className="stat-card-label">Workspace</div>
                <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>{ws.name}</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                  {Array.isArray(ws.canvases) ? ws.canvases.length : 0} canvases
                </div>
                <div className="mono" style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>{ws.id}</div>
              </div>
            ))}
          </div>

          {/* Canvas View */}
          {selectedWs && (
            <div className="card" style={{ marginTop: '16px' }}>
              <div className="card-header">
                <div>
                  <div className="card-title">{selectedWs.name} — Canvas</div>
                  <div className="card-subtitle">Drag nodes to arrange your workspace</div>
                </div>
              </div>
              <div className="card-body" style={{ minHeight: '400px', position: 'relative', background: 'var(--bg-primary)' }}>
                <div style={{
                  position: 'absolute',
                  inset: 0,
                  backgroundImage: 'radial-gradient(circle, var(--border-subtle) 1px, transparent 1px)',
                  backgroundSize: '20px 20px',
                  opacity: 0.5,
                }} />
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '400px' }}>
                  <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                    <p>Canvas viewport ready</p>
                    <p style={{ fontSize: '11px', marginTop: '4px' }}>Use the API to create canvas nodes: POST /v1/workspaces/{'{id}'}/canvas/nodes</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
