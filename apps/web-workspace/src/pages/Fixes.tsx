import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coreApi, SuggestedFix } from '../api';
import { Check, X, Undo2, Code, FileCode, Shield, GitCompare, Play } from 'lucide-react';

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
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">AI Optimization Fixes</h1>
          <p className="text-sm text-slate-400">Review suggested AI modifications, view structural code diffs, and authorize updates</p>
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

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Fixes List */}
        <div className="xl:col-span-1 bg-slate-900/40 border border-white/[0.06] rounded-xl overflow-hidden flex flex-col max-h-[600px]">
          <div className="p-4 border-b border-white/[0.06]">
            <h2 className="text-sm font-semibold text-slate-200">Suggestions Log</h2>
          </div>

          <div className="divide-y divide-white/[0.04] overflow-y-auto flex-1">
            {isLoading ? (
              <div className="p-4 space-y-3">
                <div className="skeleton h-12 w-full" />
                <div className="skeleton h-12 w-full" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="text-center py-20 text-slate-500 text-xs">
                No suggested fixes.
              </div>
            ) : (
              filtered.map((fix) => (
                <div
                  key={fix.id}
                  onClick={() => setSelectedFixId(fix.id)}
                  className={`p-4 hover:bg-slate-900/30 transition-colors cursor-pointer space-y-2 ${selectedFix?.id === fix.id ? 'bg-slate-900/50 border-l-2 border-violet-500' : ''}`}
                >
                  <div className="flex justify-between items-start gap-2">
                    <span className="text-xs font-semibold text-slate-200 line-clamp-1">{fix.description}</span>
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                      fix.status === 'approved' || fix.status === 'applied' ? 'bg-emerald-950 text-emerald-400' :
                      fix.status === 'rejected' ? 'bg-rose-950 text-rose-400' : 'bg-amber-950 text-amber-400'
                    }`}>
                      {fix.status}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 font-mono">ID: {fix.id}</p>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Selected Fix Detail & Diff Viewer */}
        <div className="xl:col-span-2 bg-slate-900/40 border border-white/[0.06] rounded-xl overflow-hidden flex flex-col min-h-[500px]">
          {selectedFix ? (
            <div className="p-5 flex-1 flex flex-col justify-between">
              <div className="space-y-4">
                {/* Header */}
                <div className="flex justify-between items-start gap-4">
                  <div>
                    <h3 className="text-base font-semibold text-slate-200">{selectedFix.description}</h3>
                    <p className="text-xs text-slate-500 mt-1">Associated Issue ID: <span className="font-mono text-slate-400">{selectedFix.issue_id}</span></p>
                  </div>

                  <div className="flex items-center gap-2">
                    {selectedFix.status === 'pending' && (
                      <>
                        <button
                          onClick={() => handleAction(selectedFix.id, 'approve')}
                          className="btn btn-sm"
                          style={{ backgroundColor: 'rgba(34, 197, 94, 0.1)', color: '#22c55e', border: '1px solid rgba(34, 197, 94, 0.3)' }}
                        >
                          <Check className="h-4 w-4" /> Approve
                        </button>
                        <button
                          onClick={() => handleAction(selectedFix.id, 'reject')}
                          className="btn btn-sm"
                          style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)' }}
                        >
                          <X className="h-4 w-4" /> Reject
                        </button>
                      </>
                    )}
                    {(selectedFix.status === 'approved' || selectedFix.status === 'applied') && (
                      <button
                        onClick={() => handleAction(selectedFix.id, 'rollback')}
                        className="btn btn-sm btn-secondary flex items-center gap-1"
                      >
                        <Undo2 className="h-4 w-4" /> Rollback
                      </button>
                    )}
                  </div>
                </div>

                {/* Diff Preview */}
                <div className="space-y-2">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block flex items-center gap-1">
                    <GitCompare className="h-3 w-3" /> Source Code Diff Analysis
                  </span>
                  <div className="border border-white/[0.06] rounded-lg bg-slate-950 p-4 font-mono text-xs text-slate-300 overflow-x-auto space-y-1.5">
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
                      <div className="text-slate-600 text-center py-12">
                        No structural code diff present for this fix.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs py-20">
              <FileCode className="h-10 w-10 text-slate-700 mb-2" />
              <p>Select a suggestion from the catalog list to review changes.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
