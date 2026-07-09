import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import ReactFlow, { Background, Controls, MiniMap } from 'reactflow';
import 'reactflow/dist/style.css';
import { workspaceApi, coreApi, Workspace, CanvasNode } from '../api';
import { Layers, Plus, Trash2, ArrowRight, PenTool, Terminal } from 'lucide-react';

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

  // Load recommendations, recent crawls, recent fixes from core APIs
  const { data: issues = [] } = useQuery({ queryKey: ['issues'], queryFn: coreApi.listIssues });
  const { data: fixes = [] } = useQuery({ queryKey: ['fixes'], queryFn: coreApi.listFixes });

  // Node creations
  const createNodeMutation = useMutation({
    mutationFn: (data: { workspaceId: string; canvas_id: string; node_type: string; label: string; x: number; y: number }) =>
      workspaceApi.createNode(data.workspaceId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      setNodeLabel('');
    },
  });

  // Node deletion
  const deleteNodeMutation = useMutation({
    mutationFn: (data: { workspaceId: string; nodeId: string; canvasId: string }) =>
      workspaceApi.deleteNode(data.workspaceId, data.nodeId, data.canvasId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
    },
  });

  const handleCreateNode = () => {
    if (!selectedWs || !nodeLabel.trim()) return;
    const canvasId = 'default-canvas';
    createNodeMutation.mutate({
      workspaceId: selectedWs.id,
      canvas_id: canvasId,
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

  // Convert canvas nodes to React Flow nodes
  // In the schemas, Workspace has `.canvases` or we create nodes associated with a canvas.
  // Wait, let's fetch the nodes. If the workspace lists canvases, or we can mock default flow nodes, let's build an interactive canvas flow list.
  const flowNodes = selectedWs?.canvases?.flatMap((c: any) => c.nodes || []) || [];

  const reactFlowNodes = flowNodes.map((n: any) => ({
    id: n.id,
    type: 'default',
    position: { x: n.x || 100, y: n.y || 100 },
    data: {
      label: (
        <div className="flex flex-col text-left text-xs text-slate-100 p-2">
          <span className="font-bold text-[9px] uppercase tracking-wider text-violet-400">{n.node_type || n.type}</span>
          <span className="font-semibold text-slate-200 mt-0.5">{n.label}</span>
          <button
            className="mt-2 text-rose-400 hover:text-rose-300 font-semibold flex items-center gap-1 text-[10px]"
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
      background: 'rgba(15, 18, 25, 0.95)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: '8px',
      width: 160,
    }
  })) || [];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">AI Canvas Workspace</h1>
          <p className="text-sm text-slate-400">Draggable node canvases mapping SEO strategies and agent workflows</p>
        </div>
        <div className="flex items-center gap-3">
          <Layers className="h-4 w-4 text-violet-400" />
          <select
            value={selectedWsId}
            onChange={(e) => setSelectedWsId(e.target.value)}
            className="bg-slate-900 border border-white/[0.08] text-slate-200 text-xs px-3 py-1.5 rounded-lg focus:outline-none focus:border-violet-500"
          >
            {workspaces.map(w => (
              <option key={w.id} value={w.id}>{w.name}</option>
            ))}
          </select>
        </div>
      </div>

      {selectedWs ? (
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
          {/* Sidebar Editor */}
          <div className="space-y-6 xl:col-span-1">
            {/* Create Node */}
            <div className="bg-slate-900/60 backdrop-blur border border-white/[0.06] rounded-xl p-5 space-y-4">
              <h2 className="text-sm font-semibold text-slate-200">Canvas Controls</h2>
              
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">Node Type</label>
                  <select
                    value={nodeType}
                    onChange={(e) => setNodeType(e.target.value)}
                    className="w-full bg-slate-950 border border-white/[0.08] text-slate-200 text-xs px-3 py-2 rounded-lg focus:outline-none"
                  >
                    <option value="goal">Cognitive Goal</option>
                    <option value="crawler">Site Crawler</option>
                    <option value="issue">Issue Node</option>
                    <option value="fix">Suggested Fix</option>
                  </select>
                </div>

                <div>
                  <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">Label</label>
                  <input
                    value={nodeLabel}
                    onChange={(e) => setNodeLabel(e.target.value)}
                    placeholder="Enter node description..."
                    className="w-full bg-slate-950 border border-white/[0.08] text-slate-200 text-xs px-3 py-2 rounded-lg focus:outline-none placeholder:text-slate-600"
                  />
                </div>

                <button
                  onClick={handleCreateNode}
                  className="w-full btn btn-primary flex justify-center gap-1.5 text-xs py-2"
                >
                  <Plus className="h-4 w-4" /> Add Node
                </button>
              </div>
            </div>

            {/* Recommendations & Overview */}
            <div className="bg-slate-900/60 backdrop-blur border border-white/[0.06] rounded-xl p-5 space-y-4">
              <h2 className="text-sm font-semibold text-slate-200">Quick Actions</h2>
              <div className="space-y-2">
                <div className="flex items-center justify-between p-3 bg-slate-950/40 rounded-lg hover:border-violet-500/40 border border-transparent transition-colors cursor-pointer">
                  <span className="text-xs text-slate-300">Run Automated SEO Fixes</span>
                  <ArrowRight className="h-4 w-4 text-slate-500" />
                </div>
                <div className="flex items-center justify-between p-3 bg-slate-950/40 rounded-lg hover:border-violet-500/40 border border-transparent transition-colors cursor-pointer">
                  <span className="text-xs text-slate-300">Publish Changes to Production</span>
                  <ArrowRight className="h-4 w-4 text-slate-500" />
                </div>
              </div>
            </div>
          </div>

          {/* Interactive Flow Canvas */}
          <div className="xl:col-span-3 bg-slate-950/60 border border-white/[0.06] rounded-xl overflow-hidden h-[600px] relative">
            {reactFlowNodes.length === 0 ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 text-xs space-y-2">
                <PenTool className="h-8 w-8 text-slate-600" />
                <p>No nodes created on this workspace canvas yet.</p>
                <p className="text-[11px] text-slate-600">Use the control panel to add draggable cards.</p>
              </div>
            ) : (
              <ReactFlow
                nodes={reactFlowNodes}
                edges={[]}
                fitView
              >
                <Background color="rgba(255,255,255,0.06)" gap={16} />
                <Controls />
                <MiniMap style={{ background: '#090e18' }} nodeColor="#7c5cfc" />
              </ReactFlow>
            )}
          </div>
        </div>
      ) : (
        <div className="text-center py-20 text-slate-500">
          No workspaces found.
        </div>
      )}
    </div>
  );
}
