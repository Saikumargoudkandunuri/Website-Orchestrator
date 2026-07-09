import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { coreApi, agenticApi, enterpriseApi, Issue, SuggestedFix, AuditEntry } from '../api';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Legend } from 'recharts';
import { AlertTriangle, CheckCircle, Clock, Shield, Activity, Target, Zap, Cpu, Server, DollarSign } from 'lucide-react';

const mockTrafficData = [
  { name: 'Mon', traffic: 4000, speed: 92 },
  { name: 'Tue', traffic: 4500, speed: 91 },
  { name: 'Wed', traffic: 5100, speed: 94 },
  { name: 'Thu', traffic: 4800, speed: 93 },
  { name: 'Fri', traffic: 6000, speed: 95 },
  { name: 'Sat', traffic: 5500, speed: 96 },
  { name: 'Sun', traffic: 5800, speed: 95 },
];

export default function DashboardPage() {
  const { data: issues = [], isLoading: loadingIssues } = useQuery<Issue[]>({
    queryKey: ['issues'],
    queryFn: coreApi.listIssues,
  });

  const { data: fixes = [], isLoading: loadingFixes } = useQuery<SuggestedFix[]>({
    queryKey: ['fixes'],
    queryFn: coreApi.listFixes,
  });

  const { data: auditLog = [], isLoading: loadingAudit } = useQuery<AuditEntry[]>({
    queryKey: ['auditLog'],
    queryFn: coreApi.listAuditLog,
  });

  const { data: goals = [], isLoading: loadingGoals } = useQuery<any[]>({
    queryKey: ['goals'],
    queryFn: agenticApi.memory.listGoals,
  });

  const { data: usage } = useQuery<Record<string, number>>({
    queryKey: ['usage'],
    queryFn: enterpriseApi.getUsage,
  });

  const criticalIssues = issues.filter(i => i.severity === 'critical' || i.severity === 'high');
  const pendingFixes = fixes.filter(f => f.status === 'pending');
  const approvedFixes = fixes.filter(f => f.status === 'approved' || f.status === 'applied');

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">Enterprise Intelligence Dashboard</h1>
          <p className="text-sm text-slate-400">Website Orchestration, SEO Automation & Agentic Governance Control Plane</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 px-3 py-1 bg-emerald-950/50 border border-emerald-800/50 text-emerald-400 rounded-full text-xs font-medium">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            System Live
          </span>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: SEO Health */}
        <div className="bg-slate-900/60 backdrop-blur border border-white/[0.06] rounded-xl p-5 hover:border-violet-500/40 transition-colors relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <Activity className="h-16 w-16 text-violet-400" />
          </div>
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">SEO Score</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-slate-100 tracking-tight">87%</span>
            <span className="text-xs font-medium text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded">+4.2%</span>
          </div>
          <p className="text-xs text-slate-400 mt-2">Core Web Vitals passing check</p>
        </div>

        {/* Metric 2: Detected Issues */}
        <div className="bg-slate-900/60 backdrop-blur border border-white/[0.06] rounded-xl p-5 hover:border-violet-500/40 transition-colors relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <AlertTriangle className="h-16 w-16 text-rose-400" />
          </div>
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Active Issues</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-slate-100 tracking-tight">{loadingIssues ? '—' : issues.length}</span>
            <span className="text-xs font-medium text-rose-400 bg-rose-950/40 px-1.5 py-0.5 rounded">{criticalIssues.length} critical</span>
          </div>
          <p className="text-xs text-slate-400 mt-2">Excludes ignored items</p>
        </div>

        {/* Metric 3: Suggested Fixes */}
        <div className="bg-slate-900/60 backdrop-blur border border-white/[0.06] rounded-xl p-5 hover:border-violet-500/40 transition-colors relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <CheckCircle className="h-16 w-16 text-emerald-400" />
          </div>
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Suggested Fixes</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-slate-100 tracking-tight">{loadingFixes ? '—' : fixes.length}</span>
            <span className="text-xs font-medium text-amber-400 bg-amber-950/40 px-1.5 py-0.5 rounded">{pendingFixes.length} pending review</span>
          </div>
          <p className="text-xs text-slate-400 mt-2">{approvedFixes.length} applied to staging</p>
        </div>

        {/* Metric 4: API Cost / Usage */}
        <div className="bg-slate-900/60 backdrop-blur border border-white/[0.06] rounded-xl p-5 hover:border-violet-500/40 transition-colors relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
            <DollarSign className="h-16 w-16 text-sky-400" />
          </div>
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Usage Cost</span>
          <div className="flex items-baseline gap-2 mt-2">
            <span className="text-3xl font-bold text-slate-100 tracking-tight">
              ${usage ? (Object.values(usage).reduce((a, b) => a + b, 0) * 0.002).toFixed(2) : '1.42'}
            </span>
            <span className="text-xs font-medium text-sky-400 bg-sky-950/40 px-1.5 py-0.5 rounded">Active</span>
          </div>
          <p className="text-xs text-slate-400 mt-2">Organized usage tracking</p>
        </div>
      </div>

      {/* Graphs Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Performance & Traffic Chart */}
        <div className="bg-slate-900/40 backdrop-blur border border-white/[0.06] rounded-xl p-5 lg:col-span-2 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-sm font-semibold text-slate-200">Traffic & Performance Health</h2>
              <p className="text-xs text-slate-500">Historical performance metrics and visitor trends</p>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={mockTrafficData}>
                <defs>
                  <linearGradient id="colorTraffic" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7c5cfc" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#7c5cfc" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip contentStyle={{ backgroundColor: '#0f1219', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px' }} />
                <Area type="monotone" dataKey="traffic" stroke="#7c5cfc" fillOpacity={1} fill="url(#colorTraffic)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Cognitive Goals & Agent Summary */}
        <div className="bg-slate-900/40 backdrop-blur border border-white/[0.06] rounded-xl p-5 space-y-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-1.5">
              <Target className="h-4 w-4 text-violet-400" />
              <h2 className="text-sm font-semibold text-slate-200">Active Goals</h2>
            </div>
            <span className="text-xs font-semibold text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">{goals.length}</span>
          </div>

          <div className="space-y-3 overflow-y-auto max-h-60 pr-1">
            {goals.length === 0 ? (
              <div className="text-center py-8 text-slate-500 text-xs">
                No active agent goals. Assign goals via the AI Copilot.
              </div>
            ) : (
              goals.map((g, i) => (
                <div key={i} className="p-3 bg-slate-950/40 border border-white/[0.03] rounded-lg space-y-1.5">
                  <div className="flex justify-between items-start gap-2">
                    <span className="text-xs font-semibold text-slate-200 line-clamp-1">{g.objective || g.description}</span>
                    <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${g.status === 'completed' ? 'bg-emerald-950 text-emerald-400' : 'bg-violet-950 text-violet-400'}`}>
                      {g.status || 'Active'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">ID: <span className="font-mono text-slate-500">{g.goal_id || `goal-${i}`}</span></p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Bottom Area: Recent Activity & Governance Pending Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Approval Fixes */}
        <div className="bg-slate-900/40 backdrop-blur border border-white/[0.06] rounded-xl overflow-hidden">
          <div className="p-5 border-bottom border-white/[0.06] flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-amber-500" />
              <h2 className="text-sm font-semibold text-slate-200">Governance Pending Queue</h2>
            </div>
            <span className="text-xs font-semibold text-amber-500 bg-amber-950/50 border border-amber-900/50 px-2 py-0.5 rounded-full">
              {pendingFixes.length} Pending
            </span>
          </div>

          <div className="divide-y divide-white/[0.04] max-h-80 overflow-y-auto">
            {pendingFixes.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-xs">
                No fixes currently require approval.
              </div>
            ) : (
              pendingFixes.map((fix) => (
                <div key={fix.id} className="p-4 flex items-center justify-between hover:bg-slate-900/20 transition-colors">
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-slate-200">{fix.description}</p>
                    <p className="text-[11px] text-slate-400">Issue ID: <span className="font-mono">{fix.issue_id}</span></p>
                  </div>
                  <span className="text-[10px] uppercase font-bold text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/30">
                    Needs Action
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Audit Trail Activity */}
        <div className="bg-slate-900/40 backdrop-blur border border-white/[0.06] rounded-xl overflow-hidden">
          <div className="p-5 border-bottom border-white/[0.06] flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-violet-400" />
              <h2 className="text-sm font-semibold text-slate-200">Audit Trail Logs</h2>
            </div>
          </div>

          <div className="p-4 timeline max-h-80 overflow-y-auto space-y-4">
            {auditLog.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-xs">
                No activity logs available.
              </div>
            ) : (
              auditLog.slice(0, 8).map((log) => (
                <div key={log.id} className="flex gap-3 relative group">
                  <div className="h-2 w-2 rounded-full bg-violet-500 mt-1.5 flex-shrink-0" />
                  <div className="space-y-0.5">
                    <p className="text-xs text-slate-300 font-medium">{log.action}</p>
                    <p className="text-[10px] text-slate-500">{log.actor} · {log.timestamp}</p>
                    {log.detail && <p className="text-[11px] text-slate-400 bg-slate-950/40 border border-white/[0.02] p-1.5 rounded mt-1 font-mono">{log.detail}</p>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
