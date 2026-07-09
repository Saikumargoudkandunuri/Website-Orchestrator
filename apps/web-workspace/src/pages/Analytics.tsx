import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { analyticsApi } from '../api';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Download, Plus, AlertCircle, BarChart3, TrendingUp, BellRing } from 'lucide-react';

const mockSpeedTrends = [
  { name: 'Run 1', speed: 840, accessibility: 82 },
  { name: 'Run 2', speed: 790, accessibility: 85 },
  { name: 'Run 3', speed: 650, accessibility: 89 },
  { name: 'Run 4', speed: 480, accessibility: 94 },
  { name: 'Run 5', speed: 410, accessibility: 96 },
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
      alert(`Successfully triggered ${format.toUpperCase()} report generation! Check your email or download directory.`);
    } catch {
      alert('Export failed. Verify service availability.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">Diagnostic Analytics Hub</h1>
          <p className="text-sm text-slate-400">Track Core Web Vitals, audit page access speeds, and configure alert thresholds</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'trends' ? ' active' : ''}`} onClick={() => setActiveTab('trends')}>Performance Trends</button>
        <button className={`tab${activeTab === 'alerts' ? ' active' : ''}`} onClick={() => setActiveTab('alerts')}>Alert Controls</button>
        <button className={`tab${activeTab === 'exports' ? ' active' : ''}`} onClick={() => setActiveTab('exports')}>Exports Center</button>
      </div>

      {activeTab === 'trends' && (
        <div className="space-y-6">
          {/* KPI summaries */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-2">
              <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Average Latency</span>
              <div className="text-2xl font-bold text-slate-100 mt-1">410ms</div>
              <span className="text-xs font-semibold text-emerald-400">-51% latency decrease</span>
            </div>
            <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-2">
              <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Accessibility Score</span>
              <div className="text-2xl font-bold text-slate-100 mt-1">96%</div>
              <span className="text-xs font-semibold text-emerald-400">+14% improvement</span>
            </div>
            <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-2">
              <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">SEO Audit Coverage</span>
              <div className="text-2xl font-bold text-slate-100 mt-1">100%</div>
              <span className="text-xs font-semibold text-slate-500">Fully covered</span>
            </div>
          </div>

          {/* Speed Trend area chart */}
          <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4">
            <h2 className="text-sm font-semibold text-slate-200">Load Latency Trend (ms)</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={mockSpeedTrends}>
                  <defs>
                    <linearGradient id="colorSpeed" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#7c5cfc" stopOpacity={0.25}/>
                      <stop offset="95%" stopColor="#7c5cfc" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                  <YAxis stroke="#64748b" fontSize={11} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f1219', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px' }} />
                  <Area type="monotone" dataKey="speed" stroke="#7c5cfc" fillOpacity={1} fill="url(#colorSpeed)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'alerts' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Configure Alert Form */}
          <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 xl:col-span-1">
            <h2 className="text-sm font-semibold text-slate-200">Create Alert Rule</h2>
            <form onSubmit={handleCreateAlert} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Rule Name</label>
                <input
                  value={alertName}
                  onChange={(e) => setAlertName(e.target.value)}
                  placeholder="e.g. Critical Latency Alert"
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Target Metric</label>
                <select
                  value={metricName}
                  onChange={(e) => setMetricName(e.target.value)}
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-200"
                >
                  <option value="page_speed_score">Page Speed Score</option>
                  <option value="seo_health_score">SEO Health Score</option>
                  <option value="accessibility_index">Accessibility Index</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Condition</label>
                  <select
                    value={operator}
                    onChange={(e) => setOperator(e.target.value)}
                    className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-200"
                  >
                    <option value=">">&gt; Greater than</option>
                    <option value="<">&lt; Less than</option>
                    <option value="=">= Equal to</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Threshold</label>
                  <input
                    type="number"
                    value={threshold}
                    onChange={(e) => setThreshold(Number(e.target.value))}
                    className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={createAlertMutation.isPending}
                className="w-full btn btn-primary flex justify-center items-center gap-1.5 py-2 text-xs"
              >
                <Plus className="h-4 w-4" /> Save Alert Rule
              </button>
            </form>
          </div>

          {/* Active Rules List */}
          <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl overflow-hidden xl:col-span-2 flex flex-col">
            <div className="p-4 border-b border-white/[0.06]">
              <h2 className="text-sm font-semibold text-slate-200">Active Alert Control Rules</h2>
            </div>
            
            <div className="overflow-x-auto flex-1">
              {loadingAlerts ? (
                <div className="p-4 space-y-3">
                  <div className="skeleton h-8 w-full" />
                  <div className="skeleton h-8 w-full" />
                </div>
              ) : alerts.length === 0 ? (
                <div className="text-center py-20 text-slate-500 text-xs">
                  No alerts currently configured.
                </div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Rule Name</th>
                      <th>Metric</th>
                      <th>Condition</th>
                      <th>Alert Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {alerts.map((a, i) => (
                      <tr key={i}>
                        <td className="text-slate-100 font-semibold">{a.rule_name || a.name || 'Alert rule'}</td>
                        <td className="mono text-xs text-slate-300">{a.metric_name || a.metric}</td>
                        <td>{a.operator} {a.threshold}</td>
                        <td>
                          <span className="badge badge-success">Monitoring</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'exports' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { format: 'pdf', title: 'Executive Summary PDF', desc: 'Download a client-ready performance summary including audits log.' },
            { format: 'csv', title: 'Performance Metrics CSV', desc: 'Download row-by-row historic performance score indices.' },
            { format: 'json', title: 'System Diagnostics JSON', desc: 'Download comprehensive structured JSON dump for internal API analysis.' },
          ].map((item) => (
            <div key={item.format} className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 flex flex-col justify-between hover:border-violet-500/40 transition-colors">
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-slate-200">{item.title}</h3>
                <p className="text-xs text-slate-400">{item.desc}</p>
              </div>
              <button
                onClick={() => handleExportReport(item.format)}
                className="w-full btn btn-secondary flex justify-center items-center gap-1.5 mt-6 py-2 text-xs font-semibold"
              >
                <Download className="h-4 w-4" /> Export as {item.format.toUpperCase()}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
