import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { coreApi, Issue } from '../api';
import { GlassCard, StatusBadge } from '../components/PremiumUI';
import { motion } from 'framer-motion';

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring", stiffness: 350, damping: 25 } }
};

export default function IssuesPage() {
  const [filter, setFilter] = useState<string>('all');

  const { data: issues = [], isLoading } = useQuery<Issue[]>({
    queryKey: ['issues'],
    queryFn: coreApi.listIssues,
  });

  const filtered = filter === 'all' ? issues : issues.filter((i) => i.severity === filter);
  const severities = ['all', 'critical', 'high', 'medium', 'low'];

  return (
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="space-y-8"
    >
      <motion.div variants={itemVariants} className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">Active Issues Log</h1>
          <p className="text-sm text-slate-500 font-semibold mt-1">Review website failures, missing parameters, and SEO issues</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-indigo-600 bg-indigo-50 border border-indigo-100 px-3 py-1 rounded-full shadow-sm">
            {issues.length} Issues Detected
          </span>
        </div>
      </motion.div>

      {/* Filters */}
      <motion.div variants={itemVariants} className="tabs">
        {severities.map((s) => (
          <button key={s} className={`tab${filter === s ? ' active' : ''}`} onClick={() => setFilter(s)}>
            {s === 'all' ? 'All Severities' : s.charAt(0).toUpperCase() + s.slice(1)}
            <span className="ml-1.5 opacity-55">
              ({s === 'all' ? issues.length : issues.filter((i) => i.severity === s).length})
            </span>
          </button>
        ))}
      </motion.div>

      <motion.div variants={itemVariants}>
        <GlassCard className="p-0 overflow-hidden">
          <div className="overflow-x-auto">
            {isLoading ? (
              <div className="p-6 space-y-4">
                <div className="skeleton h-8 w-full" />
                <div className="skeleton h-8 w-full" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-20 text-slate-400 text-xs font-semibold">
                No active issues registered. Run a crawl scan to detect issues.
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
                  {filtered.map((issue) => (
                    <tr key={issue.id}>
                      <td>
                        <StatusBadge status={issue.severity} />
                      </td>
                      <td className="text-slate-900 font-black">{issue.category}</td>
                      <td className="mono text-xs max-w-sm truncate text-indigo-600 font-bold">{issue.url}</td>
                      <td className="text-slate-600 font-semibold">{issue.description}</td>
                      <td className="text-xs text-slate-400 font-medium">{issue.detected_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </GlassCard>
      </motion.div>
    </motion.div>
  );
}
