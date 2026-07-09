import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coreApi, Issue, SuggestedFix } from '../api';
import { Search, Filter, ShieldAlert, Award, FileText, ArrowUpRight, Play, RefreshCw } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const mockTrendData = [
  { name: 'Week 1', score: 72 },
  { name: 'Week 2', score: 75 },
  { name: 'Week 3', score: 81 },
  { name: 'Week 4', score: 84 },
  { name: 'Week 5', score: 87 },
];

export default function SEOPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [selectedSeverity, setSelectedSeverity] = useState('all');

  const { data: issues = [], isLoading: loadingIssues } = useQuery<Issue[]>({
    queryKey: ['issues'],
    queryFn: coreApi.listIssues,
  });

  const { data: fixes = [] } = useQuery<SuggestedFix[]>({
    queryKey: ['fixes'],
    queryFn: coreApi.listFixes,
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => coreApi.approveFix(id, 'Bulk approved from SEO panel'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fixes'] });
    },
  });

  const filteredIssues = issues.filter(issue => {
    const matchesSearch = issue.url.toLowerCase().includes(search.toLowerCase()) || issue.description.toLowerCase().includes(search.toLowerCase());
    const matchesSeverity = selectedSeverity === 'all' || issue.severity === selectedSeverity;
    return matchesSearch && matchesSeverity;
  });

  const handleBulkApprove = () => {
    fixes.filter(f => f.status === 'pending').forEach(f => {
      approveMutation.mutate(f.id);
    });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">SEO Engine Console</h1>
          <p className="text-sm text-slate-400">Manage pages indexing, page accessibility, performance health, and AI auto-fixes</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleBulkApprove}
            className="btn btn-primary btn-sm flex items-center gap-1.5"
          >
            <Play className="h-4.5 w-4.5" /> Approve All Fixes
          </button>
        </div>
      </div>

      {/* Health Trend Graph & Summary Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-3 lg:col-span-2">
          <div className="flex justify-between items-center">
            <h2 className="text-sm font-semibold text-slate-200">Health Score Trend</h2>
            <span className="text-xs font-semibold text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded">Current: 87%</span>
          </div>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mockTrendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip contentStyle={{ backgroundColor: '#0f1219', borderColor: 'rgba(255,255,255,0.08)', borderRadius: '8px' }} />
                <Line type="monotone" dataKey="score" stroke="#7c5cfc" strokeWidth={2} dot={{ fill: '#7c5cfc' }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 flex flex-col justify-between">
          <h2 className="text-sm font-semibold text-slate-200">SEO Diagnostics</h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-slate-950/40 rounded-lg">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-rose-400" />
                <span className="text-xs text-slate-300">Errors</span>
              </div>
              <span className="text-xs font-bold text-slate-100">{issues.filter(i => i.severity === 'critical').length}</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-slate-950/40 rounded-lg">
              <div className="flex items-center gap-2">
                <Award className="h-4 w-4 text-violet-400" />
                <span className="text-xs text-slate-300">SEO Recommendations</span>
              </div>
              <span className="text-xs font-bold text-slate-100">{fixes.length}</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-slate-950/40 rounded-lg">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-sky-400" />
                <span className="text-xs text-slate-300">Pages Analyzed</span>
              </div>
              <span className="text-xs font-bold text-slate-100">124</span>
            </div>
          </div>
        </div>
      </div>

      {/* Interactive Issues Panel */}
      <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl overflow-hidden">
        <div className="p-4 border-b border-white/[0.06] flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-200">Diagnostics Log</span>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-3">
            {/* Search Box */}
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search pages or descriptions..."
                className="bg-slate-950 border border-white/[0.08] text-xs pl-9 pr-4 py-2 rounded-lg focus:outline-none w-60 placeholder:text-slate-600"
              />
            </div>

            {/* Severity Filter */}
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-slate-400" />
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
                className="bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none text-slate-200"
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
        </div>

        {/* Table Data */}
        <div className="overflow-x-auto">
          {loadingIssues ? (
            <div className="p-8 space-y-4">
              <div className="skeleton h-8 w-full" />
              <div className="skeleton h-8 w-full" />
              <div className="skeleton h-8 w-full" />
            </div>
          ) : filteredIssues.length === 0 ? (
            <div className="text-center py-20 text-slate-500 text-xs">
              No SEO issues found matching filters.
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Category</th>
                  <th>Page URL</th>
                  <th>Description</th>
                  <th>Detected At</th>
                </tr>
              </thead>
              <tbody>
                {filteredIssues.map((issue) => (
                  <tr key={issue.id}>
                    <td>
                      <span className={`badge ${issue.severity === 'critical' || issue.severity === 'high' ? 'badge-error' : issue.severity === 'medium' ? 'badge-warning' : 'badge-info'}`}>
                        {issue.severity}
                      </span>
                    </td>
                    <td className="text-slate-100 font-semibold">{issue.category}</td>
                    <td className="mono text-xs max-w-sm truncate text-slate-300">
                      <a href={issue.url} target="_blank" rel="noopener noreferrer" className="hover:text-violet-400 flex items-center gap-1">
                        {issue.url} <ArrowUpRight className="h-3 w-3" />
                      </a>
                    </td>
                    <td>{issue.description}</td>
                    <td className="text-xs text-slate-500">{issue.detected_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
