import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactFlow, { Background, Controls } from 'reactflow';
import 'reactflow/dist/style.css';
import { automationApi } from '../api';
import { Plus, Clock, Activity, Settings, ArrowRight } from 'lucide-react';
import { GlassCard, AnimatedButton, GlassInput, StatusBadge, AISummaryPanel } from '../components/PremiumUI';
import { motion } from 'framer-motion';

const workflowNodes = [
  {
    id: 'start',
    type: 'input',
    data: { label: '▶ Start Trigger (Schedule/Webhook)' },
    position: { x: 50, y: 150 },
    style: { background: 'rgba(255, 255, 255, 0.95)', border: '1px solid rgba(0,0,0,0.06)', color: '#0f172a', fontSize: '11px', width: 180, borderRadius: '12px', fontWeight: 'bold' }
  },
  {
    id: 'crawl',
    data: { label: '🕸 Crawl Web Site pages' },
    position: { x: 280, y: 150 },
    style: { background: 'rgba(255, 255, 255, 0.95)', border: '1px solid rgba(0,0,0,0.06)', color: '#0f172a', fontSize: '11px', width: 180, borderRadius: '12px', fontWeight: 'bold' }
  },
  {
    id: 'check',
    data: { label: '🔍 Run SEO & Quality Checks' },
    position: { x: 510, y: 150 },
    style: { background: 'rgba(255, 255, 255, 0.95)', border: '1px solid rgba(0,0,0,0.06)', color: '#0f172a', fontSize: '11px', width: 180, borderRadius: '12px', fontWeight: 'bold' }
  },
  {
    id: 'fix',
    data: { label: '✨ Generate AI Code Fixes' },
    position: { x: 740, y: 150 },
    style: { background: 'rgba(255, 255, 255, 0.95)', border: '1px solid rgba(0,0,0,0.06)', color: '#0f172a', fontSize: '11px', width: 180, borderRadius: '12px', fontWeight: 'bold' }
  },
  {
    id: 'governance',
    type: 'output',
    data: { label: '🛡 Governance approval' },
    position: { x: 970, y: 150 },
    style: { background: 'rgba(255, 255, 255, 0.95)', border: '1px solid rgba(0,0,0,0.06)', color: '#0f172a', fontSize: '11px', width: 180, borderRadius: '12px', fontWeight: 'bold' }
  }
];

const workflowEdges = [
  { id: 'e-start-crawl', source: 'start', target: 'crawl', animated: true, style: { stroke: '#6366f1', strokeWidth: 2.5 } },
  { id: 'e-crawl-check', source: 'crawl', target: 'check', animated: true, style: { stroke: '#6366f1', strokeWidth: 2.5 } },
  { id: 'e-check-fix', source: 'check', target: 'fix', animated: true, style: { stroke: '#6366f1', strokeWidth: 2.5 } },
  { id: 'e-fix-gov', source: 'fix', target: 'governance', animated: true, style: { stroke: '#6366f1', strokeWidth: 2.5 } },
];

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring", stiffness: 350, damping: 25 } }
};

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
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="space-y-8"
    >
      <motion.div variants={itemVariants} className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">Automation Studio</h1>
          <p className="text-sm text-slate-500 font-semibold mt-1">Design automated crawling, checks verification, and release publish flows</p>
        </div>
      </motion.div>

      {/* Tabs */}
      <motion.div variants={itemVariants} className="tabs">
        <button className={`tab${activeTab === 'builder' ? ' active' : ''}`} onClick={() => setActiveTab('builder')}>Workflow Builder</button>
        <button className={`tab${activeTab === 'library' ? ' active' : ''}`} onClick={() => setActiveTab('library')}>Templates Library</button>
        <button className={`tab${activeTab === 'history' ? ' active' : ''}`} onClick={() => setActiveTab('history')}>Executions History</button>
      </motion.div>

      {/* AI Summary Panel */}
      <motion.div variants={itemVariants}>
        <AISummaryPanel
          insights={[
            "Automation builder connects crawler scans directly with AI patch generation loops.",
            "Workflow executions enforce a mandatory governance checkpoint before code modifications are applied.",
            "Visual node templates are configured to execute in chronological alignment: Crawl → Check → Fix."
          ]}
          metrics={[
            { label: "Execution Success Rate", value: "98.8%", trend: "Calculated across runs" },
            { label: "Optimization Score", value: "95/100", trend: "Highly stable template loops" }
          ]}
          thoughts={[
            "Listening for automated scheduling cron expressions...",
            "Preparing execution edges maps...",
            "Ensuring local workspace lock holds before pipeline fires..."
          ]}
        />
      </motion.div>

      {activeTab === 'builder' && (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">
          {/* Creator form */}
          <motion.div variants={itemVariants} className="xl:col-span-1">
            <GlassCard className="space-y-4">
              <h2 className="text-sm font-bold text-slate-800">Create Custom Loop</h2>
              <form onSubmit={handleCreateWorkflow} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Workflow Name</label>
                  <GlassInput
                    value={workflowName}
                    onChange={(e) => setWorkflowName(e.target.value)}
                    placeholder="e.g. Production Auto-Fixer"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Description</label>
                  <GlassInput
                    value={workflowDesc}
                    onChange={(e) => setWorkflowDesc(e.target.value)}
                    placeholder="Summarize loop objective..."
                  />
                </div>

                <AnimatedButton
                  type="submit"
                  disabled={createWfMutation.isPending}
                  variant="primary"
                  className="w-full py-3"
                >
                  <Plus className="h-4.5 w-4.5" /> Save Loop Definition
                </AnimatedButton>
              </form>
            </GlassCard>
          </motion.div>

          {/* Visual flow canvas */}
          <motion.div variants={itemVariants} className="xl:col-span-3 bg-white/60 border border-slate-200/80 rounded-2xl h-[450px] overflow-hidden relative shadow-md">
            <div className="absolute top-4 left-4 z-10 text-[10px] bg-white border border-slate-200 px-3 py-1.5 rounded-xl text-slate-600 font-bold shadow-sm">
              Live Loop: Crawl → Check → Fix → Governance
            </div>
            <ReactFlow
              nodes={workflowNodes}
              edges={workflowEdges}
              fitView
            >
              <Background color="rgba(99,102,241,0.06)" gap={16} />
              <Controls />
            </ReactFlow>
          </motion.div>
        </div>
      )}

      {activeTab === 'library' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[
            { name: 'Weekly SEO Audit', desc: 'Runs crawl scans and outputs diagnostic metrics every Monday.', trigger: 'Scheduled (Cron)', icon: Clock },
            { name: 'Staging Auto-Publisher', desc: 'Triggers on code changes, audits changes, and auto-publishes if healthy.', trigger: 'Staging Trigger', icon: Activity },
            { name: 'Critical Release Loop', desc: 'Continuously monitors site health and rolls back breaking releases.', trigger: 'Live Alert Trigger', icon: Settings },
          ].map((t, idx) => (
            <motion.div key={idx} variants={itemVariants}>
              <div className="bg-white/80 border border-slate-200/80 rounded-2xl p-6 flex flex-col justify-between hover:border-indigo-400/50 transition-colors shadow-sm h-full">
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-indigo-50 rounded-xl border border-indigo-100/50 text-indigo-600">
                      <t.icon className="h-5 w-5" />
                    </div>
                    <h3 className="text-sm font-bold text-slate-800">{t.name}</h3>
                  </div>
                  <p className="text-xs text-slate-500 font-semibold leading-relaxed mt-2">{t.desc}</p>
                </div>

                <div className="flex items-center justify-between mt-5 pt-4 border-t border-slate-100">
                  <span className="text-[9.5px] font-extrabold uppercase tracking-widest text-slate-400 bg-slate-50 px-2 py-0.5 rounded border border-slate-100">{t.trigger}</span>
                  <button className="text-xs text-indigo-600 hover:text-indigo-700 font-bold flex items-center gap-1 cursor-pointer border-none bg-transparent">
                    Activate <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {activeTab === 'history' && (
        <motion.div variants={itemVariants}>
          <GlassCard className="p-0 overflow-hidden">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Execution ID</th>
                  <th>Workflow Name</th>
                  <th>Status</th>
                  <th>Duration</th>
                  <th>Crawl Date</th>
                </tr>
              </thead>
              <tbody>
                {mockHistory.map((h) => (
                  <tr key={h.id}>
                    <td className="mono text-xs text-indigo-600 font-bold">{h.id}</td>
                    <td className="text-slate-900 font-black leading-tight">{h.name}</td>
                    <td>
                      <StatusBadge status={h.status} />
                    </td>
                    <td className="text-xs text-slate-600 font-semibold">{h.duration}</td>
                    <td className="text-xs text-slate-400 font-medium">{h.date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
        </motion.div>
      )}
    </motion.div>
  );
}
