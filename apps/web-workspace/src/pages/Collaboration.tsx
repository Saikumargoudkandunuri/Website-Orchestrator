import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { collabApi } from '../api';
import { MessageSquare, Bell, Plus, Send } from 'lucide-react';
import { GlassCard, AnimatedButton, GlassInput, StatusBadge, AISummaryPanel } from '../components/PremiumUI';
import { motion } from 'framer-motion';

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring", stiffness: 350, damping: 25 } }
};

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
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="space-y-8"
    >
      <motion.div variants={itemVariants} className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">Collaboration Center</h1>
          <p className="text-sm text-slate-500 font-semibold mt-1">Discuss fixes with teams, review choices log, and track alert notices</p>
        </div>
      </motion.div>

      {/* Tabs */}
      <motion.div variants={itemVariants} className="tabs">
        <button className={`tab${activeTab === 'threads' ? ' active' : ''}`} onClick={() => setActiveTab('threads')}>Discussion Threads</button>
        <button className={`tab${activeTab === 'decisions' ? ' active' : ''}`} onClick={() => setActiveTab('decisions')}>Decision Log</button>
        <button className={`tab${activeTab === 'notifications' ? ' active' : ''}`} onClick={() => setActiveTab('notifications')}>Notifications Feed</button>
      </motion.div>

      {/* AI Summary Panel */}
      <motion.div variants={itemVariants}>
        <AISummaryPanel
          insights={[
            "Reviewed discussion logs regarding local WordPress link failures.",
            "Decision trace registers 100% resolution confidence after team approval cycle.",
            "Notifications feed details active sync events triggered by directory provisions."
          ]}
          metrics={[
            { label: "Decisions Resolved", value: "Complete", trend: "Governance matching" },
            { label: "Collaboration Threads", value: "Active", trend: "Real-time responses" }
          ]}
          thoughts={[
            "Polling active workspace collaboration nodes...",
            "Comparing thread comments timeline...",
            "Validating action paths authorization..."
          ]}
        />
      </motion.div>

      {activeTab === 'threads' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Thread List Column */}
          <motion.div variants={itemVariants} className="xl:col-span-1">
            <GlassCard className="p-0 overflow-hidden flex flex-col max-h-[500px]">
              <div className="p-4 border-b border-slate-100 bg-white/50">
                <h2 className="text-sm font-bold text-slate-800">Active Threads</h2>
              </div>

              <div className="divide-y divide-slate-100 overflow-y-auto flex-1 scrollbar-thin">
                {loadingThreads ? (
                  <div className="p-4 space-y-3">
                    <div className="skeleton h-12 w-full" />
                  </div>
                ) : threads.length === 0 ? (
                  <div className="text-center py-16 text-slate-400 text-xs font-semibold">
                    No discussion threads found.
                  </div>
                ) : (
                  threads.map((t) => (
                    <div
                      key={t.id}
                      onClick={() => setSelectedThreadId(t.id)}
                      className={`p-4 hover:bg-slate-50/50 transition-colors cursor-pointer space-y-1.5 ${
                        selectedThread?.id === t.id ? 'bg-slate-50 border-l-3 border-indigo-500' : ''
                      }`}
                    >
                      <div className="text-xs font-bold text-slate-700 leading-tight">{t.title}</div>
                      <span className="text-[10px] text-slate-400 font-mono">Created by: {t.created_by}</span>
                    </div>
                  ))
                )}
              </div>

              <form onSubmit={handleCreateThread} className="p-4 border-t border-slate-100 bg-white/40 flex gap-2">
                <GlassInput
                  value={threadTitle}
                  onChange={(e) => setThreadTitle(e.target.value)}
                  placeholder="Start a thread..."
                />
                <AnimatedButton
                  type="submit"
                  disabled={createThreadMutation.isPending}
                  variant="primary"
                  className="px-3"
                >
                  <Plus className="h-4 w-4" />
                </AnimatedButton>
              </form>
            </GlassCard>
          </motion.div>

          {/* Comment Responses Panel */}
          <motion.div variants={itemVariants} className="xl:col-span-2">
            <GlassCard className="p-0 overflow-hidden flex flex-col min-h-[400px]">
              {selectedThread ? (
                <>
                  <div className="p-4 border-b border-slate-100 bg-white/50">
                    <h3 className="text-sm font-bold text-slate-800">{selectedThread.title}</h3>
                  </div>

                  <div className="flex-1 p-5 space-y-4 overflow-y-auto max-h-[320px] scrollbar-thin">
                    {loadingComments ? (
                      <div className="space-y-3">
                        <div className="skeleton h-8 w-1/2" />
                      </div>
                    ) : comments.length === 0 ? (
                      <p className="text-slate-400 text-xs text-center py-16 font-semibold">No comments posted yet. Write one below!</p>
                    ) : (
                      comments.map((c) => (
                        <div key={c.id} className="p-3.5 bg-white/70 border border-slate-200/50 rounded-2xl max-w-[85%] shadow-sm">
                          <p className="text-xs font-semibold text-slate-700">{c.body}</p>
                          <span className="text-[9.5px] text-slate-400 font-mono mt-1.5 block">Author: {c.author_id} · {c.created_at || 'just now'}</span>
                        </div>
                      ))
                    )}
                  </div>

                  <form onSubmit={handleAddComment} className="p-4 border-t border-slate-100 bg-white/40 flex gap-2">
                    <GlassInput
                      value={commentBody}
                      onChange={(e) => setCommentBody(e.target.value)}
                      placeholder="Write a comment response..."
                    />
                    <AnimatedButton
                      type="submit"
                      disabled={addCommentMutation.isPending}
                      variant="primary"
                      className="px-4"
                    >
                      <Send className="h-3.5 w-3.5" /> Post
                    </AnimatedButton>
                  </form>
                </>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-slate-400 text-xs py-20">
                  <MessageSquare className="h-10 w-10 text-slate-300 mb-2" />
                  <p className="font-bold">Select a discussion thread to review remarks.</p>
                </div>
              )}
            </GlassCard>
          </motion.div>
        </div>
      )}

      {activeTab === 'decisions' && (
        <motion.div variants={itemVariants}>
          <GlassCard className="p-0 overflow-hidden">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Decision Log ID</th>
                  <th>Objective Details</th>
                  <th>Actor</th>
                  <th>Resolution</th>
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
                    <td colSpan={5} className="text-center py-20 text-slate-400 text-xs font-semibold">No decision log logs found.</td>
                  </tr>
                ) : (
                  decisions.map((d, i) => (
                    <tr key={i}>
                      <td className="mono text-xs text-indigo-600 font-bold">{d.id || `dec-${i}`}</td>
                      <td className="text-slate-900 font-black leading-tight">{d.title || d.description}</td>
                      <td className="font-bold text-slate-700">{d.created_by || d.author}</td>
                      <td className="font-bold text-slate-700">{d.resolution || 'Approved'}</td>
                      <td>
                        <StatusBadge status={d.status || 'Resolved'} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </GlassCard>
        </motion.div>
      )}

      {activeTab === 'notifications' && (
        <motion.div variants={itemVariants}>
          <GlassCard className="space-y-4 p-5">
            <h2 className="text-sm font-bold text-slate-800">Alert Updates</h2>
            <div className="space-y-3">
              {loadingNotifications ? (
                <div className="skeleton h-12 w-full" />
              ) : notifications.length === 0 ? (
                <div className="text-slate-400 text-xs text-center py-16 font-bold">No recent notifications.</div>
              ) : (
                notifications.map((n, i) => (
                  <div key={i} className="p-3.5 bg-white border border-slate-200/60 rounded-2xl flex items-center gap-3.5 shadow-sm">
                    <Bell className="h-4.5 w-4.5 text-indigo-500" />
                    <div>
                      <span className="text-xs font-bold text-slate-800 block leading-tight">{n.title || n.message}</span>
                      <span className="text-[10px] text-slate-400 block mt-1">{n.created_at || 'recorded'}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </GlassCard>
        </motion.div>
      )}
    </motion.div>
  );
}
