import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { analyticsApi } from '../api';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Download, Plus, AlertCircle, BarChart3, TrendingUp, BellRing } from 'lucide-react';
import { GlassCard, AnimatedButton, GlassInput, StatusBadge } from '../components/PremiumUI';
import { motion } from 'framer-motion';

const mockSpeedTrends = [
  { name: 'Run 1', speed: 840 },
  { name: 'Run 2', speed: 790 },
  { name: 'Run 3', speed: 650 },
  { name: 'Run 4', speed: 480 },
  { name: 'Run 5', speed: 410 },
];

export default function AnalyticsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'trends' | 'alerts' | 'exports'>('trends');
  const [alertName, setAlertName] = useState('');
  const [metricName, setMetricName] = useState('page_speed_score');
  const [operator, setOperator] = useState('>');
  const [threshold, setThreshold] = useState(90);

  // Queries
  const { data: alerts = [], isLoading: loadingAlerts } = useQuery<any[]>({
    queryKey: ['analyticsAlerts'],
    queryFn: analyticsApi.listAlerts,
  });

  // Mutations
  const createAlertMutation = useMutation({
    mutationFn: (data: any) => analyticsApi.createAlert(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analyticsAlerts'] });
      setAlertName('');
      alert('Alert rule configured successfully!');
    }
  });

  const handleCreateAlert = (e: React.FormEvent) => {
    e.preventDefault();
    if (!alertName.trim()) return;
    createAlertMutation.mutate({
      rule_name: alertName,
      metric_name: metricName,
      operator: operator,
      threshold: Number(threshold),
      actions: ['email', 'webhook']
    });
  };

  const handleExportReport = async (format: string) => {
    try {
      await analyticsApi.exportReport(format, ['page_speed_score', 'seo_health_score']);
      alert(`Successfully triggered ${format.toUpperCase()} report generation!`);
    } catch {
      alert('Export failed. Verify service availability.');
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-8"
    >
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Diagnostics Analytics Hub</h1>
          <p className="text-sm text-slate-500 mt-1">Audit Core Web Vitals, speed load latency times, and configure alerts thresholds</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'trends' ? ' active' : ''}`} onClick={() => setActiveTab('trends')}>Performance Trends</button>
        <button className={`tab${activeTab === 'alerts' ? ' active' : ''}`} onClick={() => setActiveTab('alerts')}>Alert Controls</button>
        <button className={`tab${activeTab === 'exports' ? ' active' : ''}`} onClick={() => setActiveTab('exports')}>Exports Center</button>
      </div>

      {activeTab === 'trends' && (
        <div className="space-y-6">
          {/* KPI metrics */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <GlassCard className="space-y-2">
              <span className="text-xs text-slate-400 font-bold uppercase tracking-widest block">Average Latency</span>
              <div className="text-3xl font-extrabold text-slate-900 mt-1">410ms</div>
              <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100/50 inline-block">-51% decrease</span>
            </GlassCard>
            <GlassCard className="space-y-2">
              <span className="text-xs text-slate-400 font-bold uppercase tracking-widest block">Accessibility Score</span>
              <div className="text-3xl font-extrabold text-slate-900 mt-1">96%</div>
              <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100/50 inline-block">+14% increase</span>
            </GlassCard>
            <GlassCard className="space-y-2">
              <span className="text-xs text-slate-400 font-bold uppercase tracking-widest block">Audit Coverage</span>
              <div className="text-3xl font-extrabold text-slate-900 mt-1">100%</div>
              <span className="text-xs font-semibold text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full border border-slate-100 inline-block">Complete</span>
            </GlassCard>
          </div>

          {/* Load latency Recharts area chart */}
          <GlassCard className="space-y-4">
            <h2 className="text-sm font-bold text-slate-800">Load Latency Trend (ms)</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={mockSpeedTrends}>
                  <defs>
                    <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15}/>
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.03)" />
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} axisLine={false} tickLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={11} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: '#ffffff', border: '1px solid rgba(0,0,0,0.06)', borderRadius: '12px' }} />
                  <Area type="monotone" dataKey="speed" stroke="#6366f1" strokeWidth={2.5} fillOpacity={1} fill="url(#colorLatency)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        </div>
      )}

      {activeTab === 'alerts' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Configure Alert Form */}
          <GlassCard className="space-y-4 xl:col-span-1">
            <h2 className="text-sm font-bold text-slate-800">Create Alert Rule</h2>
            <form onSubmit={handleCreateAlert} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Rule Name</label>
                <GlassInput
                  value={alertName}
                  onChange={(e) => setAlertName(e.target.value)}
                  placeholder="e.g. High Latency Trigger"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Target Metric</label>
                <select
                  value={metricName}
                  onChange={(e) => setMetricName(e.target.value)}
                  className="w-full bg-white/70 border border-slate-200 text-slate-700 text-xs px-3 py-2.5 rounded-xl focus:outline-none focus:border-indigo-500"
                >
                  <option value="page_speed_score">Page Speed Score</option>
                  <option value="seo_health_score">SEO Health Score</option>
                  <option value="accessibility_index">Accessibility Index</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Condition</label>
                  <select
                    value={operator}
                    onChange={(e) => setOperator(e.target.value)}
                    className="w-full bg-white/70 border border-slate-200 text-slate-700 text-xs px-3 py-2.5 rounded-xl focus:outline-none focus:border-indigo-500"
                  >
                    <option value=">">&gt; Greater than</option>
                    <option value="<">&lt; Less than</option>
                    <option value="=">= Equal to</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Threshold</label>
                  <GlassInput
                    type="number"
                    value={threshold}
                    onChange={(e) => setThreshold(Number(e.target.value))}
                  />
                </div>
              </div>

              <AnimatedButton
                type="submit"
                disabled={createAlertMutation.isPending}
                variant="primary"
                className="w-full py-2.5"
              >
                <Plus className="h-4 w-4" /> Save Alert Rule
              </AnimatedButton>
            </form>
          </GlassCard>

          {/* Active Rules List */}
          <GlassCard className="xl:col-span-2 p-0 overflow-hidden flex flex-col">
            <div className="p-4 border-b border-slate-100 bg-white/50">
              <h2 className="text-sm font-bold text-slate-800">Configured Rules</h2>
            </div>
            
            <div className="overflow-x-auto flex-1">
              {loadingAlerts ? (
                <div className="p-4 space-y-3">
                  <div className="skeleton h-8 w-full" />
                </div>
              ) : alerts.length === 0 ? (
                <div className="text-center py-20 text-slate-400 text-xs">
                  No alerts configured.
                </div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Rule Name</th>
                      <th>Metric</th>
                      <th>Condition</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {alerts.map((a, i) => (
                      <tr key={i}>
                        <td className="text-slate-900 font-bold">{a.rule_name || a.name || 'Alert rule'}</td>
                        <td className="mono text-xs text-indigo-600 font-semibold">{a.metric_name || a.metric}</td>
                        <td className="font-semibold">{a.operator} {a.threshold}</td>
                        <td>
                          <StatusBadge status="Monitoring" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </GlassCard>
        </div>
      )}

      {activeTab === 'exports' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { format: 'pdf', title: 'Executive Summary PDF', desc: 'Download a clean corporate executive diagnostics report summary.' },
            { format: 'csv', title: 'Performance Index CSV', desc: 'Download detailed structured dataset files of latency records.' },
            { format: 'json', title: 'System Diagnostics JSON', desc: 'Download structural JSON file for developer API validation.' },
          ].map((item) => (
            <GlassCard key={item.format} className="flex flex-col justify-between hover:border-indigo-400 transition-colors">
              <div className="space-y-2">
                <h3 className="text-sm font-bold text-slate-800">{item.title}</h3>
                <p className="text-xs text-slate-400 leading-relaxed">{item.desc}</p>
              </div>
              <AnimatedButton
                onClick={() => handleExportReport(item.format)}
                variant="secondary"
                className="w-full mt-6 py-2.5 flex items-center justify-center gap-1.5 font-bold"
              >
                <Download className="h-4 w-4" /> Export as {item.format.toUpperCase()}
              </AnimatedButton>
            </GlassCard>
          ))}
        </div>
      )}
    </motion.div>
  );
}
