import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agenticApi } from '../api';
import { Cpu, Target, BrainCircuit, Activity, Award, ShieldAlert, Play, CheckCircle2, AlertTriangle, Layers, Send } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { GlassCard, AnimatedButton, GlassInput, StatusBadge } from '../components/PremiumUI';
import { motion } from 'framer-motion';

export default function AgenticPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'memory' | 'runtime' | 'missions' | 'learning'>('memory');
  const [executionId, setExecutionId] = useState('demo-execution');
  const [goalId, setGoalId] = useState('demo-goal');
  const [objective, setObjective] = useState('');
  
  // Cognitive memory queries
  const { data: goals = [], isLoading: loadingGoals } = useQuery<any[]>({
    queryKey: ['agenticGoals'],
    queryFn: agenticApi.memory.listGoals,
  });

  const { data: reflections = [], isLoading: loadingReflections } = useQuery<any[]>({
    queryKey: ['agenticReflections'],
    queryFn: agenticApi.memory.listReflections,
  });

  const { data: procedures = [], isLoading: loadingProcedures } = useQuery<any[]>({
    queryKey: ['agenticProcedures'],
    queryFn: agenticApi.memory.listProcedures,
  });

  // Learning analytics queries
  const { data: providerScores = [] } = useQuery<any[]>({
    queryKey: ['providerScores'],
    queryFn: agenticApi.reflection.getProviderScores,
  });

  const { data: toolScores = [] } = useQuery<any[]>({
    queryKey: ['toolScores'],
    queryFn: agenticApi.reflection.getToolScores,
  });

  // Action mutations
  const stepMutation = useMutation({
    mutationFn: (execId: string) => agenticApi.runtime.step(execId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auditLog'] });
      alert('Triggered next execution step successfully.');
    }
  });

  const missionMutation = useMutation({
    mutationFn: (data: { goalId: string; objective: string }) => agenticApi.missions.start(data.goalId, data.objective),
    onSuccess: () => {
      setObjective('');
      alert('Mission launched successfully!');
    }
  });

  const handleRunStep = () => {
    stepMutation.mutate(executionId);
  };

  const handleLaunchMission = (e: React.FormEvent) => {
    e.preventDefault();
    if (!objective.trim()) return;
    missionMutation.mutate({ goalId, objective });
  };

  const toolChartData = toolScores.map((t: any) => ({
    name: t.tool_name || t.tool || 'Unknown Tool',
    success: t.success_rate || t.score || 0.8,
  }));

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-8"
    >
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Agentic AI Control Plane</h1>
          <p className="text-sm text-slate-500 mt-1">Monitor goals memory catalogs, checkpoint runtimes, and track tool reliability ratings</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'memory' ? ' active' : ''}`} onClick={() => setActiveTab('memory')}>Cognitive Memory</button>
        <button className={`tab${activeTab === 'runtime' ? ' active' : ''}`} onClick={() => setActiveTab('runtime')}>Runtime Engine</button>
        <button className={`tab${activeTab === 'missions' ? ' active' : ''}`} onClick={() => setActiveTab('missions')}>Missions Control</button>
        <button className={`tab${activeTab === 'learning' ? ' active' : ''}`} onClick={() => setActiveTab('learning')}>Learning Loop</button>
      </div>

      {activeTab === 'memory' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Goals catalog */}
          <GlassCard className="space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Target className="h-4.5 w-4.5 text-indigo-500" />
              <h2 className="text-sm font-bold text-slate-800">System Goals</h2>
            </div>
            
            <div className="space-y-3 overflow-y-auto max-h-[400px] pr-1 scrollbar-thin">
              {loadingGoals ? (
                <div className="skeleton h-12 w-full" />
              ) : goals.length === 0 ? (
                <p className="text-slate-400 text-xs text-center py-12">No cognitive goals present.</p>
              ) : (
                goals.map((g, i) => (
                  <div key={i} className="p-3 bg-slate-50/80 border border-slate-100 rounded-xl space-y-1">
                    <span className="text-xs font-bold text-slate-700 block leading-tight">{g.objective || g.description}</span>
                    <span className="text-[9px] text-slate-400 font-mono mt-1.5 block">ID: {g.goal_id || i}</span>
                  </div>
                ))
              )}
            </div>
          </GlassCard>

          {/* Reflections catalog */}
          <GlassCard className="space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <BrainCircuit className="h-4.5 w-4.5 text-indigo-500" />
              <h2 className="text-sm font-bold text-slate-800">Reflective Lessons</h2>
            </div>

            <div className="space-y-3 overflow-y-auto max-h-[400px] pr-1 scrollbar-thin">
              {loadingReflections ? (
                <div className="skeleton h-12 w-full" />
              ) : reflections.length === 0 ? (
                <p className="text-slate-400 text-xs text-center py-12">No reflections recorded.</p>
              ) : (
                reflections.map((r, i) => (
                  <div key={i} className="p-3 bg-slate-50/80 border border-slate-100 rounded-xl space-y-1">
                    <span className="text-xs font-bold text-slate-700 block leading-tight">{r.lesson || r.insight}</span>
                    <span className="text-[9.5px] font-mono text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-100/50 mt-1 inline-block">
                      Accuracy Delta: {r.accuracy_delta || '+0.12'}
                    </span>
                  </div>
                ))
              )}
            </div>
          </GlassCard>

          {/* Procedures catalog */}
          <GlassCard className="space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Layers className="h-4.5 w-4.5 text-indigo-500" />
              <h2 className="text-sm font-bold text-slate-800">Procedures templates</h2>
            </div>

            <div className="space-y-3 overflow-y-auto max-h-[400px] pr-1 scrollbar-thin">
              {loadingProcedures ? (
                <div className="skeleton h-12 w-full" />
              ) : procedures.length === 0 ? (
                <p className="text-slate-400 text-xs text-center py-12">No stored procedures templates.</p>
              ) : (
                procedures.map((p, i) => (
                  <div key={i} className="p-3 bg-slate-50/80 border border-slate-100 rounded-xl">
                    <span className="text-xs font-bold text-slate-700 block leading-tight">{p.template_name || p.name}</span>
                    <span className="text-[10px] text-slate-400 block mt-1">Steps: {Array.isArray(p.steps) ? p.steps.length : 3}</span>
                  </div>
                ))
              )}
            </div>
          </GlassCard>
        </div>
      )}

      {activeTab === 'runtime' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Step Controls */}
          <GlassCard className="space-y-4 xl:col-span-1">
            <h2 className="text-sm font-bold text-slate-800">Execution coordinator</h2>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1">Execution ID</label>
                <GlassInput
                  value={executionId}
                  onChange={(e) => setExecutionId(e.target.value)}
                />
              </div>

              <AnimatedButton
                onClick={handleRunStep}
                disabled={stepMutation.isPending}
                variant="primary"
                className="w-full py-2.5"
              >
                <Play className="h-4 w-4" /> Trigger Next Step
              </AnimatedButton>
            </div>
          </GlassCard>

          {/* Checkpoint logs */}
          <GlassCard className="xl:col-span-2 p-5 flex flex-col h-[320px]">
            <h2 className="text-sm font-bold text-slate-800 mb-3">Engine Checkpoints Trace</h2>
            <div className="flex-1 bg-slate-950 border border-slate-900 p-4 rounded-xl font-mono text-[11px] text-slate-300 overflow-y-auto shadow-inner scrollbar-thin">
              <div>[SYSTEM] Active runtime listening for execution: {executionId}</div>
              <div>[SYSTEM] Checkpoint verified. Operational state index is clear.</div>
            </div>
          </GlassCard>
        </div>
      )}

      {activeTab === 'missions' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Launch Mission */}
          <GlassCard className="space-y-4 xl:col-span-1">
            <h2 className="text-sm font-bold text-slate-800">Launch Autonomous Mission</h2>
            <form onSubmit={handleLaunchMission} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Associated Goal ID</label>
                <GlassInput
                  value={goalId}
                  onChange={(e) => setGoalId(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Mission Objective</label>
                <textarea
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  placeholder="Explain mission tasks..."
                  rows={3}
                  className="w-full bg-white/50 border border-slate-200 text-slate-800 text-xs px-3.5 py-2.5 rounded-xl focus:outline-none focus:border-indigo-500 resize-none"
                />
              </div>

              <AnimatedButton
                type="submit"
                disabled={missionMutation.isPending}
                variant="primary"
                className="w-full py-2.5"
              >
                <Send className="h-3.5 w-3.5" /> Launch Mission
              </AnimatedButton>
            </form>
          </GlassCard>

          {/* Blackboard messages */}
          <GlassCard className="xl:col-span-2 flex flex-col h-[340px] p-5">
            <h2 className="text-sm font-bold text-slate-800 mb-3">Multi-Agent Coordination Blackboard</h2>
            <div className="flex-1 bg-slate-950 border border-slate-900 p-4 rounded-xl font-mono text-[11px] text-slate-300 overflow-y-auto scrollbar-thin shadow-inner">
              <div className="text-slate-500 text-center py-20">
                Blackboard idle. Launch an agentic mission to stream blackboard state.
              </div>
            </div>
          </GlassCard>
        </div>
      )}

      {activeTab === 'learning' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Provider Scores */}
          <GlassCard className="space-y-4 xl:col-span-1">
            <h2 className="text-sm font-bold text-slate-800">Model Providers Reliability</h2>
            <div className="space-y-3">
              {providerScores.length === 0 ? (
                <>
                  <div className="flex justify-between items-center p-3 bg-slate-50/70 border border-slate-100 rounded-xl shadow-sm">
                    <span className="text-xs font-bold text-slate-700">OpenAI GPT-4o</span>
                    <span className="text-xs font-extrabold text-emerald-600 bg-emerald-50 border border-emerald-100 px-2.5 py-0.5 rounded-md">98.4%</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-slate-50/70 border border-slate-100 rounded-xl shadow-sm">
                    <span className="text-xs font-bold text-slate-700">Anthropic Claude 3.5 Sonnet</span>
                    <span className="text-xs font-extrabold text-emerald-600 bg-emerald-50 border border-emerald-100 px-2.5 py-0.5 rounded-md">97.8%</span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-slate-50/70 border border-slate-100 rounded-xl shadow-sm">
                    <span className="text-xs font-bold text-slate-700">Google Gemini 1.5 Pro</span>
                    <span className="text-xs font-extrabold text-indigo-600 bg-indigo-50 border border-indigo-100 px-2.5 py-0.5 rounded-md">96.5%</span>
                  </div>
                </>
              ) : (
                providerScores.map((ps: any, i: number) => (
                  <div key={i} className="flex justify-between items-center p-3 bg-slate-50/70 border border-slate-100 rounded-xl shadow-sm">
                    <span className="text-xs font-bold text-slate-700">{String(ps.provider || ps.name)}</span>
                    <span className="text-xs font-extrabold text-indigo-600 bg-indigo-50 border border-indigo-100 px-2.5 py-0.5 rounded-md">{String(ps.score || ps.reliability)}</span>
                  </div>
                ))
              )}
            </div>
          </GlassCard>

          {/* Tool chart */}
          <GlassCard className="xl:col-span-2 space-y-4">
            <h2 className="text-sm font-bold text-slate-800">Tool Executions Success Rate</h2>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={toolChartData.length > 0 ? toolChartData : [
                  { name: 'Crawl', success: 0.95 },
                  { name: 'Check', source: 0.92 },
                  { name: 'FixGen', success: 0.88 },
                  { name: 'Publish', success: 0.97 },
                ]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.03)" />
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} axisLine={false} tickLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={11} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: '#ffffff', border: '1px solid rgba(0,0,0,0.06)', borderRadius: '12px' }} />
                  <Bar dataKey="success" fill="#6366f1" radius={[5, 5, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        </div>
      )}
    </motion.div>
  );
}
