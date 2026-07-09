import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { collabApi } from '../api';
import { MessageSquare, CheckSquare, Bell, ArrowRight, Plus, Send, RefreshCw } from 'lucide-react';

export default function CollaborationPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'threads' | 'decisions' | 'notifications'>('threads');
  
  // Custom thread additions states
  const [threadTitle, setThreadTitle] = useState('');
  const [selectedThreadId, setSelectedThreadId] = useState<string>('');
  const [commentBody, setCommentBody] = useState('');

  // Queries
  const { data: decisions = [], isLoading: loadingDecisions } = useQuery<any[]>({
    queryKey: ['decisions'],
    queryFn: collabApi.listDecisions,
  });

  const { data: notifications = [], isLoading: loadingNotifications } = useQuery<any[]>({
    queryKey: ['notifications'],
    queryFn: collabApi.listNotifications,
  });

  // Since we require target node ID for listThreads, let's use a dummy node for standard discussion target
  const targetNodeId = 'demo-seo-node';
  const { data: threads = [], isLoading: loadingThreads } = useQuery<any[]>({
    queryKey: ['threads', targetNodeId],
    queryFn: () => collabApi.listThreads(targetNodeId),
  });

  const selectedThread = threads.find(t => t.id === selectedThreadId) || threads[0];

  const { data: comments = [], isLoading: loadingComments } = useQuery<any[]>({
    queryKey: ['comments', selectedThread?.id],
    queryFn: () => (selectedThread ? collabApi.listComments(selectedThread.id) : Promise.resolve([])),
    enabled: !!selectedThread,
  });

  // Mutations
  const createThreadMutation = useMutation({
    mutationFn: (data: { title: string; target_node_id: string; created_by: string }) =>
      collabApi.createThread(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['threads', targetNodeId] });
      setThreadTitle('');
      setSelectedThreadId(data.id as string);
    }
  });

  const addCommentMutation = useMutation({
    mutationFn: (data: { threadId: string; author_id: string; body: string }) =>
      collabApi.addComment(data.threadId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', selectedThread?.id] });
      setCommentBody('');
    }
  });

  const handleCreateThread = (e: React.FormEvent) => {
    e.preventDefault();
    if (!threadTitle.trim()) return;
    createThreadMutation.mutate({
      title: threadTitle,
      target_node_id: targetNodeId,
      created_by: 'demo-user',
    });
  };

  const handleAddComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedThread || !commentBody.trim()) return;
    addCommentMutation.mutate({
      threadId: selectedThread.id,
      author_id: 'demo-user',
      body: commentBody,
    });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">Collaboration Center</h1>
          <p className="text-sm text-slate-400">Team threads, decision logs history, and system change notifications</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'threads' ? ' active' : ''}`} onClick={() => setActiveTab('threads')}>Discussions Threads</button>
        <button className={`tab${activeTab === 'decisions' ? ' active' : ''}`} onClick={() => setActiveTab('decisions')}>Decision Log</button>
        <button className={`tab${activeTab === 'notifications' ? ' active' : ''}`} onClick={() => setActiveTab('notifications')}>Notifications Feed</button>
      </div>

      {activeTab === 'threads' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Thread List Column */}
          <div className="xl:col-span-1 bg-slate-900/40 border border-white/[0.06] rounded-xl flex flex-col max-h-[500px]">
            <div className="p-4 border-b border-white/[0.06] flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-200">Active Threads</h2>
            </div>

            {/* List */}
            <div className="divide-y divide-white/[0.04] overflow-y-auto flex-1">
              {loadingThreads ? (
                <div className="p-4 space-y-3">
                  <div className="skeleton h-12 w-full" />
                </div>
              ) : threads.length === 0 ? (
                <div className="text-center py-12 text-slate-500 text-xs">
                  No discussion threads created for this target.
                </div>
              ) : (
                threads.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => setSelectedThreadId(t.id)}
                    className={`p-4 hover:bg-slate-900/30 transition-colors cursor-pointer space-y-1 ${
                      selectedThread?.id === t.id ? 'bg-slate-900/50 border-l-2 border-violet-500' : ''
                    }`}
                  >
                    <div className="text-xs font-semibold text-slate-200">{t.title}</div>
                    <span className="text-[10px] text-slate-500 font-mono">Created by: {t.created_by}</span>
                  </div>
                ))
              )}
            </div>

            {/* Create Thread Input Form */}
            <form onSubmit={handleCreateThread} className="p-4 border-t border-white/[0.06] flex gap-2">
              <input
                value={threadTitle}
                onChange={(e) => setThreadTitle(e.target.value)}
                placeholder="Start a thread..."
                className="flex-1 bg-slate-950 border border-white/[0.08] text-xs px-3 py-1.5 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
              />
              <button
                type="submit"
                disabled={createThreadMutation.isPending}
                className="btn btn-primary px-3 text-xs"
              >
                <Plus className="h-4 w-4" />
              </button>
            </form>
          </div>

          {/* Selected Thread Comments Display Panel */}
          <div className="xl:col-span-2 bg-slate-900/40 border border-white/[0.06] rounded-xl flex flex-col min-h-[400px]">
            {selectedThread ? (
              <>
                <div className="p-4 border-b border-white/[0.06]">
                  <h3 className="text-sm font-semibold text-slate-200">{selectedThread.title}</h3>
                </div>

                <div className="flex-1 p-4 space-y-4 overflow-y-auto max-h-[300px]">
                  {loadingComments ? (
                    <div className="space-y-3">
                      <div className="skeleton h-8 w-1/2" />
                      <div className="skeleton h-8 w-2/3 ml-auto" />
                    </div>
                  ) : comments.length === 0 ? (
                    <p className="text-slate-600 text-xs text-center py-12">No comments posted yet. Write one below!</p>
                  ) : (
                    comments.map((c) => (
                      <div key={c.id} className="p-3 bg-slate-950/40 border border-white/[0.02] rounded-lg max-w-[85%]">
                        <p className="text-xs text-slate-300">{c.body}</p>
                        <span className="text-[9px] text-slate-500 font-mono mt-1.5 block">Author: {c.author_id} · {c.created_at || 'just now'}</span>
                      </div>
                    ))
                  )}
                </div>

                <form onSubmit={handleAddComment} className="p-4 border-t border-white/[0.06] flex gap-2">
                  <input
                    value={commentBody}
                    onChange={(e) => setCommentBody(e.target.value)}
                    placeholder="Write a comment response..."
                    className="flex-1 bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                  />
                  <button
                    type="submit"
                    disabled={addCommentMutation.isPending}
                    className="btn btn-primary px-4 text-xs flex items-center gap-1"
                  >
                    <Send className="h-3.5 w-3.5" /> Post
                  </button>
                </form>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-xs">
                <MessageSquare className="h-10 w-10 text-slate-700 mb-2" />
                <p>Select an active discussion thread to review remarks.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'decisions' && (
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl overflow-hidden">
          <table className="data-table">
            <thead>
              <tr>
                <th>Decision Log ID</th>
                <th>Objective Details</th>
                <th>Actor</th>
                <th>Resolution Decision</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loadingDecisions ? (
                <tr>
                  <td colSpan={5} className="p-4"><div className="skeleton h-8 w-full" /></td>
                </tr>
              ) : decisions.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-20 text-slate-500 text-xs">No decision log logs found.</td>
                </tr>
              ) : (
                decisions.map((d, i) => (
                  <tr key={i}>
                    <td className="mono text-xs text-slate-300">{d.id || `dec-${i}`}</td>
                    <td className="text-slate-100 font-semibold">{d.title || d.description}</td>
                    <td>{d.created_by || d.author}</td>
                    <td>{d.resolution || 'Approved'}</td>
                    <td>
                      <span className="badge badge-success">{d.status || 'Resolved'}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'notifications' && (
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4">
          <h2 className="text-sm font-semibold text-slate-200">Alert Updates</h2>
          <div className="space-y-3">
            {loadingNotifications ? (
              <div className="skeleton h-12 w-full" />
            ) : notifications.length === 0 ? (
              <div className="text-slate-500 text-xs text-center py-10">No recent notifications logs.</div>
            ) : (
              notifications.map((n, i) => (
                <div key={i} className="p-3 bg-slate-950/40 border border-white/[0.03] rounded-lg flex items-center gap-3">
                  <Bell className="h-4 w-4 text-violet-400" />
                  <div>
                    <span className="text-xs font-semibold text-slate-200 block">{n.title || n.message}</span>
                    <span className="text-[10px] text-slate-500 block mt-0.5">{n.created_at || 'recorded'}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
