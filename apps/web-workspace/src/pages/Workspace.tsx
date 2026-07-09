import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow';
import 'reactflow/dist/style.css';
import { workspaceApi, Workspace } from '../api';
import { Layers, Plus, Trash2, ArrowRight, PenTool } from 'lucide-react';
import { GlassCard, AnimatedButton, GlassInput } from '../components/PremiumUI';
import { motion } from 'framer-motion';

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring", stiffness: 350, damping: 25 } }
};

export default function WorkspacePage() {
  const queryClient = useQueryClient();
  const [selectedWsId, setSelectedWsId] = useState<string>('');
  const [nodeType, setNodeType] = useState<string>('goal');
  const [nodeLabel, setNodeLabel] = useState<string>('');

  const { data: workspaces = [], isLoading: loadingWs } = useQuery<Workspace[]>({
    queryKey: ['workspaces'],
    queryFn: workspaceApi.list,
  });

  const selectedWs = workspaces.find(w => w.id === selectedWsId) || workspaces[0];

  useEffect(() => {
    if (workspaces.length > 0 && !selectedWsId) {
      setSelectedWsId(workspaces[0].id);
    }
  }, [workspaces, selectedWsId]);

  const createNodeMutation = useMutation({
    mutationFn: (data: { workspaceId: string; canvas_id: string; node_type: string; label: string; x: number; y: number }) =>
      workspaceApi.createNode(data.workspaceId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      setNodeLabel('');
    },
  });

  const deleteNodeMutation = useMutation({
    mutationFn: (data: { workspaceId: string; nodeId: string; canvasId: string }) =>
      workspaceApi.deleteNode(data.workspaceId, data.nodeId, data.canvasId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
    },
  });

  const handleCreateNode = () => {
    if (!selectedWs || !nodeLabel.trim()) return;
    createNodeMutation.mutate({
      workspaceId: selectedWs.id,
      canvas_id: 'default-canvas',
      node_type: nodeType,
      label: nodeLabel,
      x: 100 + Math.random() * 200,
      y: 100 + Math.random() * 200,
    });
  };

  const handleDeleteNode = (nodeId: string) => {
    if (!selectedWs) return;
    deleteNodeMutation.mutate({
      workspaceId: selectedWs.id,
      nodeId,
      canvasId: 'default-canvas',
    });
  };

  const flowNodes = selectedWs?.canvases?.flatMap((c: any) => c.nodes || []) || [];

  const reactFlowNodes = flowNodes.map((n: any) => ({
    id: n.id,
    type: 'default',
    position: { x: n.x || 100, y: n.y || 100 },
    data: {
      label: (
        <div className="flex flex-col text-left p-1 text-slate-800 space-y-1.5 font-sans">
          <div className="flex justify-between items-center">
            <span className="font-extrabold text-[8px] uppercase tracking-wider text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-100/50">
              {n.node_type || n.type}
            </span>
          </div>
          <span className="font-bold text-[11px] text-slate-800 leading-tight">{n.label}</span>
          <button
            className="text-rose-500 hover:text-rose-600 font-bold flex items-center gap-0.5 text-[9px] mt-1 cursor-pointer border-none bg-transparent"
            onClick={(e) => {
              e.stopPropagation();
              handleDeleteNode(n.id);
            }}
          >
            <Trash2 className="h-3 w-3" /> Remove
          </button>
        </div>
      )
    },
    style: {
      background: 'rgba(255, 255, 255, 0.95)',
      backdropFilter: 'blur(12px)',
      border: '1px solid rgba(0,0,0,0.06)',
      boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.03)',
      borderRadius: '14px',
      width: 160,
    }
  })) || [];

  return (
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="space-y-8"
    >
      {/* Page Header */}
      <motion.div variants={itemVariants} className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">AI Canvas Workspace</h1>
          <p className="text-sm text-slate-500 font-semibold mt-1">Configure layout canvases mapping structural crawler nodes and objectives</p>
        </div>
        <div className="flex items-center gap-3">
          <Layers className="h-4.5 w-4.5 text-indigo-500" />
          <select
            value={selectedWsId}
            onChange={(e) => setSelectedWsId(e.target.value)}
            className="bg-white border border-slate-200 text-slate-700 text-xs px-3.5 py-2 rounded-xl focus:outline-none focus:border-indigo-500 font-extrabold shadow-sm cursor-pointer"
          >
            {workspaces.map(w => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </div>
      </motion.div>

      {selectedWs ? (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">
          {/* Sidebar controls */}
          <motion.div variants={itemVariants} className="space-y-6 xl:col-span-1">
            {/* Create Node */}
            <GlassCard className="space-y-4">
              <h2 className="text-sm font-extrabold text-slate-800">Canvas Controls</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest block mb-1.5">Node Type</label>
                  <select
                    value={nodeType}
                    onChange={(e) => setNodeType(e.target.value)}
                    className="w-full bg-white/70 border border-slate-200 text-slate-700 text-xs px-3.5 py-2.5 rounded-xl focus:outline-none cursor-pointer font-semibold"
                  >
                    <option value="goal">Cognitive Goal</option>
                    <option value="crawler">Site Crawler</option>
                    <option value="issue">Issue Node</option>
                    <option value="fix">Suggested Fix</option>
                  </select>
                </div>

                <div>
                  <label className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest block mb-1.5">Label</label>
                  <GlassInput
                    value={nodeLabel}
                    onChange={(e) => setNodeLabel(e.target.value)}
                    placeholder="Enter node description..."
                  />
                </div>

                <AnimatedButton
                  onClick={handleCreateNode}
                  variant="primary"
                  className="w-full py-3"
                >
                  <Plus className="h-4.5 w-4.5" /> Add Node
                </AnimatedButton>
              </div>
            </GlassCard>

            {/* Quick Actions */}
            <GlassCard className="space-y-4">
              <h2 className="text-sm font-extrabold text-slate-800">Quick Actions</h2>
              <div className="space-y-2">
                <div className="flex items-center justify-between p-3.5 bg-white/60 hover:bg-white rounded-xl border border-slate-100 hover:border-indigo-200 transition-all cursor-pointer shadow-sm">
                  <span className="text-xs font-bold text-slate-700">Run Automated SEO Fixes</span>
                  <ArrowRight className="h-4 w-4 text-slate-400" />
                </div>
                <div className="flex items-center justify-between p-3.5 bg-white/60 hover:bg-white rounded-xl border border-slate-100 hover:border-indigo-200 transition-all cursor-pointer shadow-sm">
                  <span className="text-xs font-bold text-slate-700">Publish Changes to Production</span>
                  <ArrowRight className="h-4 w-4 text-slate-400" />
                </div>
              </div>
            </GlassCard>
          </motion.div>

          {/* Draggable flows viewport */}
          <motion.div variants={itemVariants} className="xl:col-span-3 bg-white/60 border border-slate-200/80 rounded-2xl overflow-hidden h-[580px] relative shadow-md">
            {reactFlowNodes.length === 0 ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 text-xs space-y-2">
                <PenTool className="h-8 w-8 text-slate-300" />
                <p className="font-bold">Canvas workspace empty.</p>
                <p className="text-[11px] text-slate-400">Use the control panel to add draggable cards.</p>
              </div>
            ) : (
              <ReactFlow
                nodes={reactFlowNodes}
                edges={[]}
                fitView
              >
                <Background color="rgba(99,102,241,0.06)" gap={16} />
                <Controls />
                <MiniMap style={{ background: '#ffffff', border: '1px solid rgba(0,0,0,0.05)', borderRadius: '12px' }} nodeColor="#6366f1" />
              </ReactFlow>
            )}
          </motion.div>
        </div>
      ) : (
        <div className="text-center py-20 text-slate-500 font-semibold">
          No workspaces found.
        </div>
      )}
    </motion.div>
  );
}
