import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactFlow, { Background, Controls } from 'reactflow';
import 'reactflow/dist/style.css';
import { agenticApi } from '../api';
import { Search, Database, Share2, HelpCircle, Eye } from 'lucide-react';

const initialNodes = [
  {
    id: 'org',
    data: { label: '🏢 Organization: Acme' },
    position: { x: 250, y: 50 },
    style: { background: 'rgba(15, 18, 25, 0.95)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', fontSize: '11px', width: 160 }
  },
  {
    id: 'wp',
    data: { label: '🎨 Site: wordpress.org' },
    position: { x: 100, y: 150 },
    style: { background: 'rgba(15, 18, 25, 0.95)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', fontSize: '11px', width: 160 }
  },
  {
    id: 'c1',
    data: { label: '🕸 Crawl Job #104' },
    position: { x: 280, y: 250 },
    style: { background: 'rgba(15, 18, 25, 0.95)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', fontSize: '11px', width: 160 }
  },
  {
    id: 'i1',
    data: { label: '⚠️ Issue: Broken Link' },
    position: { x: 420, y: 150 },
    style: { background: 'rgba(15, 18, 25, 0.95)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', fontSize: '11px', width: 160 }
  }
];

const initialEdges = [
  { id: 'e1', source: 'org', target: 'wp', style: { stroke: '#7c5cfc' } },
  { id: 'e2', source: 'wp', target: 'c1', style: { stroke: '#7c5cfc' } },
  { id: 'e3', source: 'c1', target: 'i1', style: { stroke: '#7c5cfc' } },
];

export default function KnowledgeGraphPage() {
  const [query, setQuery] = useState('');
  const [searchTriggered, setSearchTriggered] = useState(false);

  // Search query
  const { data: searchResults = [], isLoading } = useQuery<any[]>({
    queryKey: ['memorySearch', query],
    queryFn: () => agenticApi.memory.search(query),
    enabled: searchTriggered && query.trim().length > 0,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchTriggered(true);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">Enterprise Knowledge Graph</h1>
          <p className="text-sm text-slate-400">Trace reasoning links, semantic facts, and entity structures discovered by autonomous agent scans</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* Search Panel */}
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 xl:col-span-1">
          <div className="flex items-center gap-2">
            <Database className="h-4.5 w-4.5 text-violet-400" />
            <h2 className="text-sm font-semibold text-slate-200">Semantic Search</h2>
          </div>

          <form onSubmit={handleSearch} className="space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
              <input
                value={query}
                onChange={(e) => { setQuery(e.target.value); setSearchTriggered(false); }}
                placeholder="Query semantic memory..."
                className="w-full bg-slate-950 border border-white/[0.08] text-xs pl-9 pr-4 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
              />
            </div>
            <button type="submit" className="w-full btn btn-primary py-2 text-xs font-semibold">
              Search Memory
            </button>
          </form>

          {/* Results list */}
          <div className="space-y-2 mt-4 overflow-y-auto max-h-[300px]">
            {isLoading && <div className="skeleton h-10 w-full" />}
            {searchTriggered && searchResults.length === 0 && !isLoading && (
              <p className="text-slate-500 text-[11px] text-center">No matching entities found in memory.</p>
            )}
            {searchResults.map((item, idx) => (
              <div key={idx} className="p-3 bg-slate-950/40 border border-white/[0.03] rounded-lg">
                <span className="text-xs font-semibold text-slate-200 block">{item.fact || item.label || JSON.stringify(item)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Visual Graph View */}
        <div className="xl:col-span-3 bg-slate-950/60 border border-white/[0.06] rounded-xl h-[500px] overflow-hidden relative">
          <div className="absolute top-4 left-4 z-10 text-[10px] bg-slate-900 border border-white/[0.08] px-2.5 py-1.5 rounded text-slate-400 font-mono">
            Reasoning Links Canvas
          </div>
          <ReactFlow
            nodes={initialNodes}
            edges={initialEdges}
            fitView
          >
            <Background color="rgba(255,255,255,0.06)" gap={16} />
            <Controls />
          </ReactFlow>
        </div>
      </div>
    </div>
  );
}
