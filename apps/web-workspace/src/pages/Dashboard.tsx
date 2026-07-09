import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { coreApi, agenticApi, enterpriseApi, Issue, SuggestedFix, AuditEntry } from '../api';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { AlertTriangle, CheckCircle, Clock, Shield, Activity, Target, DollarSign } from 'lucide-react';
import { GlassCard, GlassCard3D, MetricCard, StatusBadge, TimelineItem } from '../components/PremiumUI';
import { motion } from 'framer-motion';

const mockTrafficData = [
  { name: 'Mon', traffic: 4000 },
  { name: 'Tue', traffic: 4500 },
  { name: 'Wed', traffic: 5100 },
  { name: 'Thu', traffic: 4800 },
  { name: 'Fri', traffic: 6000 },
  { name: 'Sat', traffic: 5500 },
  { name: 'Sun', traffic: 5800 },
];

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08
    }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring", stiffness: 350, damping: 25 } }
};

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

  return (
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="space-y-8"
    >
      {/* Page Header */}
      <motion.div variants={itemVariants} className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">Enterprise Console</h1>
          <p className="text-sm text-slate-500 font-semibold mt-1">Autonomous orchestration, real-time website crawler audit & governance dashboard</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-2.5 px-4 py-1.5 bg-indigo-50 border border-indigo-100 text-indigo-600 rounded-full text-xs font-bold shadow-sm">
            <span className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
            Control Plane Active
          </span>
        </div>
      </motion.div>

      {/* Metric Cards Grid */}
      <motion.div variants={itemVariants} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          label="SEO Index Score"
          value="87%"
          change="+4.2%"
          changeType="positive"
          description="Average response parameters"
          icon={<Activity className="h-5 w-5" />}
        />
        <MetricCard
          label="Active Issues"
          value={loadingIssues ? '—' : issues.length}
          change={`${criticalIssues.length} critical`}
          changeType={criticalIssues.length > 0 ? 'negative' : 'neutral'}
          description="Excludes ignored violations"
          icon={<AlertTriangle className="h-5 w-5" />}
        />
        <MetricCard
          label="Suggested Fixes"
          value={loadingFixes ? '—' : fixes.length}
          change={`${pendingFixes.length} pending`}
          changeType="neutral"
          description="Awaiting governance decision"
          icon={<CheckCircle className="h-5 w-5" />}
        />
        <MetricCard
          label="Operational Cost"
          value={usage ? `$${(Object.values(usage).reduce((a, b) => a + b, 0) * 0.002).toFixed(2)}` : '$1.42'}
          change="Syncing"
          changeType="positive"
          description="Monthly database consumption"
          icon={<DollarSign className="h-5 w-5" />}
        />
      </motion.div>

      {/* Graphs Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Performance & Traffic Chart */}
        <motion.div variants={itemVariants} className="lg:col-span-2">
          <GlassCard3D className="space-y-6">
            <div>
              <h2 className="text-base font-extrabold text-slate-800">Crawl Response Performance</h2>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">Average crawler speed trends across execution steps</p>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={mockTrafficData}>
                  <defs>
                    <linearGradient id="colorTraffic" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15}/>
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.02)" />
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} fontWeight={600} axisLine={false} tickLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={11} fontWeight={600} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: '#ffffff', border: '1px solid rgba(0,0,0,0.06)', borderRadius: '12px', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.03)' }} />
                  <Area type="monotone" dataKey="traffic" stroke="#6366f1" strokeWidth={3} fillOpacity={1} fill="url(#colorTraffic)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </GlassCard3D>
        </motion.div>

        {/* Cognitive Goals */}
        <motion.div variants={itemVariants}>
          <GlassCard className="space-y-6 h-full flex flex-col justify-between">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Target className="h-4.5 w-4.5 text-indigo-500" />
                <h2 className="text-base font-extrabold text-slate-800">Active Goals</h2>
              </div>
              <span className="text-xs font-bold text-slate-500 bg-slate-100/80 px-2 py-0.5 rounded-full">{goals.length}</span>
            </div>

            <div className="space-y-3 overflow-y-auto max-h-60 pr-1 flex-1 mt-4 scrollbar-thin">
              {loadingGoals ? (
                <div className="skeleton h-12 w-full" />
              ) : goals.length === 0 ? (
                <div className="text-center py-16 text-slate-400 text-xs font-semibold">
                  No active agentic objectives.
                </div>
              ) : (
                goals.map((g, i) => (
                  <div key={i} className="p-3.5 bg-white/70 border border-slate-200/50 rounded-xl space-y-1.5 hover:bg-white hover:border-indigo-200 hover:shadow-sm transition-all">
                    <div className="flex justify-between items-start gap-2">
                      <span className="text-xs font-bold text-slate-700 leading-tight">{g.objective || g.description}</span>
                      <span className="text-[9px] uppercase font-black px-2 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100/50">
                        {g.status || 'Active'}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono block">ID: {g.goal_id || `goal-${i}`}</span>
                  </div>
                ))
              )}
            </div>
          </GlassCard>
        </motion.div>
      </div>

      {/* Bottom Area: Recent Activity & Governance Pending Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pending Approval Fixes */}
        <motion.div variants={itemVariants}>
          <GlassCard className="p-0 overflow-hidden flex flex-col justify-between h-full min-h-[340px]">
            <div className="p-5 border-b border-slate-100 flex justify-between items-center bg-white/50">
              <div className="flex items-center gap-2">
                <Shield className="h-4.5 w-4.5 text-indigo-500" />
                <h2 className="text-sm font-extrabold text-slate-800">Governance Pending Queue</h2>
              </div>
              <span className="text-xs font-bold text-amber-600 bg-amber-50 border border-amber-100 px-2.5 py-0.5 rounded-full">
                {pendingFixes.length} Actions
              </span>
            </div>

            <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto flex-1 scrollbar-thin">
              {pendingFixes.length === 0 ? (
                <div className="text-center py-20 text-slate-400 text-xs font-semibold">
                  No suggested fixes require review.
                </div>
              ) : (
                pendingFixes.map((fix) => (
                  <div key={fix.id} className="p-4 flex items-center justify-between hover:bg-slate-50/40 transition-colors">
                    <div className="space-y-1">
                      <p className="text-xs font-bold text-slate-700 leading-snug">{fix.description}</p>
                      <p className="text-[10px] text-slate-400 font-semibold">Issue ID: <span className="font-mono text-indigo-600">{fix.issue_id}</span></p>
                    </div>
                    <span className="text-[10px] font-extrabold text-amber-600 bg-amber-50 border border-amber-100 px-2 py-0.5 rounded">
                      Pending
                    </span>
                  </div>
                ))
              )}
            </div>
          </GlassCard>
        </motion.div>

        {/* Audit Trail Activity */}
        <motion.div variants={itemVariants}>
          <GlassCard className="p-0 overflow-hidden min-h-[340px] flex flex-col">
            <div className="p-5 border-b border-slate-100 bg-white/50">
              <div className="flex items-center gap-2">
                <Clock className="h-4.5 w-4.5 text-indigo-500" />
                <h2 className="text-sm font-extrabold text-slate-800">Audit Trail Activity</h2>
              </div>
            </div>

            <div className="p-5 timeline max-h-80 overflow-y-auto space-y-4 flex-1 scrollbar-thin">
              {loadingAudit ? (
                <div className="skeleton h-12 w-full" />
              ) : auditLog.length === 0 ? (
                <div className="text-center py-20 text-slate-400 text-xs font-semibold">
                  No audit entries registered.
                </div>
              ) : (
                auditLog.slice(0, 5).map((log) => (
                  <TimelineItem
                    key={log.id}
                    title={log.action}
                    time={`${log.actor} · ${log.timestamp}`}
                    detail={log.detail}
                    type={log.action.includes('approve') ? 'success' : log.action.includes('reject') ? 'error' : 'info'}
                  />
                ))
              )}
            </div>
          </GlassCard>
        </motion.div>
      </div>
    </motion.div>
  );
}
