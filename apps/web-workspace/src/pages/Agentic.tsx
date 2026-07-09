import React, { useState, useEffect } from 'react';
import { agenticApi } from '../api';

export default function AgenticPage() {
  const [activeTab, setActiveTab] = useState<'memory' | 'runtime' | 'missions' | 'learning'>('memory');
  const [goals, setGoals] = useState<Record<string, unknown>[]>([]);
  const [reflections, setReflections] = useState<Record<string, unknown>[]>([]);
  const [procedures, setProcedures] = useState<Record<string, unknown>[]>([]);
  const [providerScores, setProviderScores] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      agenticApi.memory.listGoals(),
      agenticApi.memory.listReflections(),
      agenticApi.memory.listProcedures(),
      agenticApi.learning.providerScores(),
    ]).then(([g, r, p, ps]) => {
      if (g.status === 'fulfilled') setGoals(g.value);
      if (r.status === 'fulfilled') setReflections(r.value);
      if (p.status === 'fulfilled') setProcedures(p.value);
      if (ps.status === 'fulfilled') setProviderScores(ps.value);
      setLoading(false);
    });
  }, []);

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Agentic AI</h1>
          <p>Memory, runtime, missions, and learning systems for autonomous AI agents</p>
        </div>
        <div className="page-header-actions">
          <span className="badge badge-info">AI-Powered</span>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'memory' ? ' active' : ''}`} onClick={() => setActiveTab('memory')}>Memory</button>
        <button className={`tab${activeTab === 'runtime' ? ' active' : ''}`} onClick={() => setActiveTab('runtime')}>Runtime</button>
        <button className={`tab${activeTab === 'missions' ? ' active' : ''}`} onClick={() => setActiveTab('missions')}>Missions</button>
        <button className={`tab${activeTab === 'learning' ? ' active' : ''}`} onClick={() => setActiveTab('learning')}>Learning</button>
      </div>

      {activeTab === 'memory' && (
        <div className="grid-3">
          <div className="card">
            <div className="card-header">
              <div className="card-title">Goals</div>
              <span className="badge badge-default">{goals.length}</span>
            </div>
            <div className="card-body">
              {loading ? (
                <div className="skeleton" style={{ height: '60px' }} />
              ) : goals.length === 0 ? (
                <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No goals recorded yet.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {goals.slice(0, 5).map((g, i) => (
                    <div key={i} style={{ padding: '8px 12px', background: 'var(--bg-hover)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {String(g.description || g.goal_id || JSON.stringify(g).slice(0, 80))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Reflections</div>
              <span className="badge badge-default">{reflections.length}</span>
            </div>
            <div className="card-body">
              {loading ? (
                <div className="skeleton" style={{ height: '60px' }} />
              ) : reflections.length === 0 ? (
                <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No reflections yet.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {reflections.slice(0, 5).map((r, i) => (
                    <div key={i} style={{ padding: '8px 12px', background: 'var(--bg-hover)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {String(r.lesson || r.insight || JSON.stringify(r).slice(0, 80))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Procedures</div>
              <span className="badge badge-default">{procedures.length}</span>
            </div>
            <div className="card-body">
              {loading ? (
                <div className="skeleton" style={{ height: '60px' }} />
              ) : procedures.length === 0 ? (
                <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No procedures stored.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {procedures.slice(0, 5).map((p, i) => (
                    <div key={i} style={{ padding: '8px 12px', background: 'var(--bg-hover)', borderRadius: 'var(--radius-md)', fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {String(p.template_name || p.name || JSON.stringify(p).slice(0, 80))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'runtime' && (
        <div className="card">
          <div className="card-body">
            <div className="empty-state">
              <div className="empty-state-icon">🤖</div>
              <h3>Execution Runtime</h3>
              <p>Start an execution plan to see runtime state, checkpoints, and step history.</p>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '8px' }}>
                Use POST /agentic/runtime/start to begin a plan execution.
              </p>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'missions' && (
        <div className="card">
          <div className="card-body">
            <div className="empty-state">
              <div className="empty-state-icon">🎯</div>
              <h3>Mission Control</h3>
              <p>Launch multi-agent missions, view agent coordination, blackboard state, and mission metrics.</p>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'learning' && (
        <div className="grid-2">
          <div className="card">
            <div className="card-header">
              <div className="card-title">Provider Scores</div>
            </div>
            <div className="card-body">
              {providerScores.length === 0 ? (
                <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>No provider scores available yet.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {providerScores.map((ps, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--bg-hover)', borderRadius: 'var(--radius-md)' }}>
                      <span style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{String(ps.provider || ps.name || `Provider ${i + 1}`)}</span>
                      <span className="badge badge-success">{String(ps.score || ps.reliability || '—')}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Experience Summary</div>
            </div>
            <div className="card-body">
              <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                The learning system tracks provider performance, tool reliability, and confidence calibration across all agentic executions.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
