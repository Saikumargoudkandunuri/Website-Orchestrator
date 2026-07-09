import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactFlow, { Background, Controls } from 'reactflow';
import 'reactflow/dist/style.css';
import { automationApi } from '../api';
import { Play, Plus, BookOpen, Clock, Activity, Settings, HelpCircle, ArrowRight } from 'lucide-react';

const workflowNodes = [
  {
    id: 'start',
    type: 'input',
    data: { label: '▶ Start Trigger (Schedule/Webhook)' },
    position: { x: 50, y: 150 },
    style: { background: 'rgba(15, 18, 25, 0.95)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', fontSize: '11px', width: 180 }
  },
  {
    id: 'crawl',
    data: { label: '🕸 Crawl Web Site pages' },
    position: { x: 280, y: 150 },
    style: { background: 'rgba(15, 18, 25, 0.95)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', fontSize: '11px', width: 180 }
  },
  {
    id: 'check',
    data: { label: '🔍 Run SEO & Quality Checks' },
    position: { x: 510, y: 150 },
    style: { background: 'rgba(15, 18, 25, 0.95)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', fontSize: '11px', width: 180 }
  },
  {
    id: 'fix',
    data: { label: '✨ Generate AI Code Fixes' },
    position: { x: 740, y: 150 },
    style: { background: 'rgba(15, 18, 25, 0.95)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', fontSize: '11px', width: 180 }
  },
  {
    id: 'governance',
    type: 'output',
    data: { label: '🛡 Governance approval & Publish' },
    position: { x: 970, y: 150 },
    style: { background: 'rgba(15, 18, 25, 0.95)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', fontSize: '11px', width: 180 }
  }
];

const workflowEdges = [
  { id: 'e-start-crawl', source: 'start', target: 'crawl', animated: true, style: { stroke: '#7c5cfc' } },
  { id: 'e-crawl-check', source: 'crawl', target: 'check', animated: true, style: { stroke: '#7c5cfc' } },
  { id: 'e-check-fix', source: 'check', target: 'fix', animated: true, style: { stroke: '#7c5cfc' } },
  { id: 'e-fix-gov', source: 'fix', target: 'governance', animated: true, style: { stroke: '#7c5cfc' } },
];

export default function AutomationPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'builder' | 'library' | 'history'>('builder');
  const [workflowName, setWorkflowName] = useState('');
  const [workflowDesc, setWorkflowDesc] = useState('');

  // Mutation to create workflow
  const createWfMutation = useMutation({
    mutationFn: (data: { name: string; description: string; trigger_type: string; steps: any[] }) =>
      automationApi.createWorkflow(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      setWorkflowName('');
      setWorkflowDesc('');
      alert('Workflow created successfully!');
    }
  });

  const handleCreateWorkflow = (e: React.FormEvent) => {
    e.preventDefault();
    if (!workflowName.trim()) return;
    createWfMutation.mutate({
      name: workflowName,
      description: workflowDesc,
      trigger_type: 'manual',
      steps: [
        { action: 'crawl', params: { max_pages: 50 } },
        { action: 'check', params: {} },
        { action: 'fix', params: {} }
      ]
    });
  };

  const mockHistory = [
    { id: 'exec-1', name: 'Site Monitor Audit', status: 'Active', duration: '2m 14s', date: '2026-07-09 09:30' },
    { id: 'exec-2', name: 'Weekly SEO Audit', status: 'Completed', duration: '5m 40s', date: '2026-07-08 14:10' },
    { id: 'exec-3', name: 'Weekly SEO Audit', status: 'Failed', duration: '12s', date: '2026-07-01 14:00' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">Automation Studio</h1>
          <p className="text-sm text-slate-400">Design automated loops for crawling, auditing, fixing, and verifying site adjustments</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'builder' ? ' active' : ''}`} onClick={() => setActiveTab('builder')}>Workflow Builder</button>
        <button className={`tab${activeTab === 'library' ? ' active' : ''}`} onClick={() => setActiveTab('library')}>Templates Library</button>
        <button className={`tab${activeTab === 'history' ? ' active' : ''}`} onClick={() => setActiveTab('history')}>Executions History</button>
      </div>

      {activeTab === 'builder' && (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
          {/* Creator form */}
          <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 xl:col-span-1">
            <h2 className="text-sm font-semibold text-slate-200">Create Custom Loop</h2>
            <form onSubmit={handleCreateWorkflow} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Workflow Name</label>
                <input
                  value={workflowName}
                  onChange={(e) => setWorkflowName(e.target.value)}
                  placeholder="e.g. Production Auto-Fixer"
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Description</label>
                <input
                  value={workflowDesc}
                  onChange={(e) => setWorkflowDesc(e.target.value)}
                  placeholder="Summarize what this loop does..."
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <button
                type="submit"
                disabled={createWfMutation.isPending}
                className="w-full btn btn-primary flex justify-center items-center gap-1.5 py-2 text-xs"
              >
                <Plus className="h-4 w-4" /> Save Loop Definition
              </button>
            </form>
          </div>

          {/* Visual flow canvas builder */}
          <div className="xl:col-span-3 bg-slate-950/60 border border-white/[0.06] rounded-xl h-[450px] overflow-hidden relative">
            <div className="absolute top-4 left-4 z-10 text-[10px] bg-slate-900 border border-white/[0.08] px-2.5 py-1.5 rounded text-slate-400 font-mono">
              Live Loop: Crawl → Check → Fix → Publish
            </div>
            <ReactFlow
              nodes={workflowNodes}
              edges={workflowEdges}
              fitView
            >
              <Background color="rgba(255,255,255,0.06)" gap={16} />
              <Controls />
            </ReactFlow>
          </div>
        </div>
      )}

      {activeTab === 'library' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { name: 'Weekly SEO Audit', desc: 'Runs crawl scans and outputs diagnostic metrics every Monday.', trigger: 'Scheduled (Cron)', icon: Clock },
            { name: 'Staging Auto-Publisher', desc: 'Triggers on code changes, audits changes, and auto-publishes if healthy.', trigger: 'Staging Trigger', icon: Activity },
            { name: 'Critical Remediation Loop', desc: 'Continuously monitors site health and rolls back breaking releases.', trigger: 'Live Alert Trigger', icon: Settings },
          ].map((t, idx) => (
            <div key={idx} className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 flex flex-col justify-between group hover:border-violet-500/40 transition-colors">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <div className="p-2 bg-violet-950/40 rounded-lg border border-violet-800/40 text-violet-400">
                    <t.icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-sm font-semibold text-slate-200">{t.name}</h3>
                </div>
                <p className="text-xs text-slate-400 mt-2">{t.desc}</p>
              </div>

              <div className="flex items-center justify-between mt-4">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 bg-slate-950 px-2 py-0.5 rounded border border-white/[0.03]">{t.trigger}</span>
                <button className="text-xs text-violet-400 hover:text-violet-300 font-semibold flex items-center gap-1">
                  Activate <ArrowRight className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'history' && (
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl overflow-hidden">
          <table className="data-table">
            <thead>
              <tr>
                <th>Execution ID</th>
                <th>Workflow Name</th>
                <th>Status</th>
                <th>Execution Duration</th>
                <th>Crawl Date</th>
              </tr>
            </thead>
            <tbody>
              {mockHistory.map((h) => (
                <tr key={h.id}>
                  <td className="mono text-xs text-slate-300">{h.id}</td>
                  <td className="text-slate-100 font-semibold">{h.name}</td>
                  <td>
                    <span className={`badge ${
                      h.status === 'Completed' ? 'badge-success' :
                      h.status === 'Failed' ? 'badge-error' : 'badge-warning'
                    }`}>
                      {h.status}
                    </span>
                  </td>
                  <td className="text-xs text-slate-300">{h.duration}</td>
                  <td className="text-xs text-slate-500">{h.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
