import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coreApi, Issue, SuggestedFix } from '../api';
import { Search, Filter, ShieldAlert, Award, FileText, ArrowUpRight, Play } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { GlassCard, AnimatedButton, GlassInput, StatusBadge } from '../components/PremiumUI';
import { motion } from 'framer-motion';

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
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-8"
    >
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">SEO Engine</h1>
          <p className="text-sm text-slate-500 mt-1">Manage index parameters, speed performance scores, accessibility index, and auto-fixes</p>
        </div>
        <div className="flex items-center gap-2">
          <AnimatedButton
            onClick={handleBulkApprove}
            variant="primary"
            className="flex items-center gap-1.5"
          >
            <Play className="h-4.5 w-4.5" /> Approve All Fixes
          </AnimatedButton>
        </div>
      </div>

      {/* Health Trend Graph & Summary Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <GlassCard className="lg:col-span-2 space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-sm font-bold text-slate-800">Health Index Trend</h2>
            <span className="text-xs font-bold text-emerald-600 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded">Current: 87%</span>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mockTrendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.03)" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} axisLine={false} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#ffffff', border: '1px solid rgba(0,0,0,0.06)', borderRadius: '12px' }} />
                <Line type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2.5} dot={{ fill: '#6366f1', strokeWidth: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard className="space-y-4 flex flex-col justify-between">
          <h2 className="text-sm font-bold text-slate-800">Diagnostics Summary</h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3.5 bg-slate-50/70 border border-slate-100 rounded-xl">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-rose-500" />
                <span className="text-xs font-semibold text-slate-600">Active Errors</span>
              </div>
              <span className="text-xs font-extrabold text-slate-800">{issues.filter(i => i.severity === 'critical').length}</span>
            </div>
            <div className="flex justify-between items-center p-3.5 bg-slate-50/70 border border-slate-100 rounded-xl">
              <div className="flex items-center gap-2">
                <Award className="h-4 w-4 text-indigo-500" />
                <span className="text-xs font-semibold text-slate-600">AI Recommendations</span>
              </div>
              <span className="text-xs font-extrabold text-slate-800">{fixes.length}</span>
            </div>
            <div className="flex justify-between items-center p-3.5 bg-slate-50/70 border border-slate-100 rounded-xl">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-sky-500" />
                <span className="text-xs font-semibold text-slate-600">Scanned Pages</span>
              </div>
              <span className="text-xs font-extrabold text-slate-800">124</span>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Issues Panel */}
      <GlassCard className="p-0 overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
          <span className="text-sm font-bold text-slate-800">Diagnostics Log</span>

          <div className="flex flex-col sm:flex-row items-center gap-3">
            {/* Search Box */}
            <div className="relative">
              <Search className="absolute left-3.5 top-3 h-4 w-4 text-slate-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search URL or violation description..."
                className="bg-white/80 border border-slate-200 text-xs pl-10 pr-4 py-2 rounded-xl focus:outline-none focus:border-indigo-500 w-64"
              />
            </div>

            {/* Severity Filter */}
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-slate-400" />
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
                className="bg-white/80 border border-slate-200 text-xs px-3 py-2 rounded-xl focus:outline-none text-slate-700 font-semibold shadow-sm"
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
            <div className="p-6 space-y-4">
              <div className="skeleton h-8 w-full" />
              <div className="skeleton h-8 w-full" />
            </div>
          ) : filteredIssues.length === 0 ? (
            <div className="text-center py-20 text-slate-400 text-xs">
              No SEO issues present.
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
                      <StatusBadge status={issue.severity} />
                    </td>
                    <td className="text-slate-900 font-bold">{issue.category}</td>
                    <td className="mono text-xs max-w-sm truncate text-indigo-600 font-semibold">
                      <a href={issue.url} target="_blank" rel="noopener noreferrer" className="hover:underline flex items-center gap-1">
                        {issue.url} <ArrowUpRight className="h-3.5 w-3.5" />
                      </a>
                    </td>
                    <td className="text-slate-600 font-medium">{issue.description}</td>
                    <td className="text-xs text-slate-400">{issue.detected_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </GlassCard>
    </motion.div>
  );
}
