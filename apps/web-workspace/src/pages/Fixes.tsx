import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coreApi, SuggestedFix } from '../api';
import { Check, X, Undo2, Code, FileCode, Shield, GitCompare, Play } from 'lucide-react';
import { GlassCard, AnimatedButton, StatusBadge } from '../components/PremiumUI';
import { motion } from 'framer-motion';

export default function FixesPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState('all');
  const [selectedFixId, setSelectedFixId] = useState<string>('');

  const { data: fixes = [], isLoading } = useQuery<SuggestedFix[]>({
    queryKey: ['fixes'],
    queryFn: coreApi.listFixes,
  });

  const selectedFix = fixes.find(f => f.id === selectedFixId) || fixes[0];

  const handleAction = async (id: string, action: 'approve' | 'reject' | 'rollback') => {
    try {
      if (action === 'approve') await coreApi.approveFix(id, 'Console approval');
      else if (action === 'reject') await coreApi.rejectFix(id, 'Console rejection');
      else await coreApi.rollbackFix(id, 'Console rollback');
      queryClient.invalidateQueries({ queryKey: ['fixes'] });
      queryClient.invalidateQueries({ queryKey: ['auditLog'] });
      queryClient.invalidateQueries({ queryKey: ['issues'] });
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Action failed');
    }
  };

  const filtered = filter === 'all' ? fixes : fixes.filter(f => f.status === filter);
  const statuses = ['all', 'pending', 'approved', 'applied', 'rejected'];

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-8"
    >
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">AI Optimization Fixes</h1>
          <p className="text-sm text-slate-500 mt-1">Review suggestions code adjustments and verify rollback status controls</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {statuses.map((s) => (
          <button key={s} className={`tab${filter === s ? ' active' : ''}`} onClick={() => setFilter(s)}>
            {s.charAt(0).toUpperCase() + s.slice(1)}
            <span className="ml-1.5 opacity-55">
              ({s === 'all' ? fixes.length : fixes.filter(f => f.status === s).length})
            </span>
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Fixes List */}
        <GlassCard className="xl:col-span-1 p-0 overflow-hidden flex flex-col max-h-[580px]">
          <div className="p-4 border-b border-slate-100 bg-white/50">
            <h2 className="text-sm font-bold text-slate-800">Suggestions Log</h2>
          </div>

          <div className="divide-y divide-slate-100 overflow-y-auto flex-1 scrollbar-thin">
            {isLoading ? (
              <div className="p-4 space-y-3">
                <div className="skeleton h-12 w-full" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-20 text-slate-400 text-xs">
                No suggested fixes found.
              </div>
            ) : (
              filtered.map((fix) => (
                <div
                  key={fix.id}
                  onClick={() => setSelectedFixId(fix.id)}
                  className={`p-4 hover:bg-slate-50/50 transition-colors cursor-pointer space-y-2 ${selectedFix?.id === fix.id ? 'bg-slate-50 border-l-3 border-indigo-500' : ''}`}
                >
                  <div className="flex justify-between items-start gap-2">
                    <span className="text-xs font-bold text-slate-700 line-clamp-1">{fix.description}</span>
                    <StatusBadge status={fix.status} />
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono block">ID: {fix.id}</span>
                </div>
              ))
            )}
          </div>
        </GlassCard>

        {/* Selected Fix Detail & Diff Viewer */}
        <GlassCard className="xl:col-span-2 p-5 flex flex-col justify-between min-h-[500px]">
          {selectedFix ? (
            <div className="space-y-6">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-5">
                <div>
                  <h3 className="text-base font-bold text-slate-800">{selectedFix.description}</h3>
                  <p className="text-xs text-slate-400 mt-1">Associated Issue: <span className="font-mono text-indigo-600">{selectedFix.issue_id}</span></p>
                </div>

                <div className="flex items-center gap-2">
                  {selectedFix.status === 'pending' && (
                    <>
                      <AnimatedButton
                        onClick={() => handleAction(selectedFix.id, 'approve')}
                        variant="primary"
                        className="py-2"
                      >
                        <Check className="h-4.5 w-4.5" /> Approve
                      </AnimatedButton>
                      <AnimatedButton
                        onClick={() => handleAction(selectedFix.id, 'reject')}
                        className="py-2 text-rose-600 hover:bg-rose-50"
                      >
                        <X className="h-4.5 w-4.5" /> Reject
                      </AnimatedButton>
                    </>
                  )}
                  {(selectedFix.status === 'approved' || selectedFix.status === 'applied') && (
                    <AnimatedButton
                      onClick={() => handleAction(selectedFix.id, 'rollback')}
                      variant="secondary"
                      className="py-2"
                    >
                      <Undo2 className="h-4.5 w-4.5" /> Rollback
                    </AnimatedButton>
                  )}
                </div>
              </div>

              {/* Diff Preview */}
              <div className="space-y-3">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block flex items-center gap-1.5">
                  <GitCompare className="h-4 w-4 text-slate-500" /> Source Code Diff Analysis
                </span>
                <div className="border border-slate-200/80 rounded-xl bg-slate-950 p-4 font-mono text-xs text-slate-300 overflow-x-auto space-y-1.5 shadow-inner">
                  {selectedFix.diff ? (
                    selectedFix.diff.split('\n').map((line, i) => (
                      <div
                        key={i}
                        className={`p-0.5 rounded ${
                          line.startsWith('+') ? 'bg-emerald-950/40 text-emerald-400' :
                          line.startsWith('-') ? 'bg-rose-950/40 text-rose-400' :
                          line.startsWith('@@') ? 'text-violet-400 font-semibold' : 'text-slate-400'
                        }`}
                      >
                        {line}
                      </div>
                    ))
                  ) : (
                    <div className="text-slate-500 text-center py-16">
                      No structural diff present for this fix.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-400 text-xs py-20">
              <FileCode className="h-10 w-10 text-slate-300 mb-2" />
              <p className="font-semibold">Select a suggested fix configuration card to review.</p>
            </div>
          )}
        </GlassCard>
      </div>
    </motion.div>
  );
}
