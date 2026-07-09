import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactFlow, { Background, Controls } from 'reactflow';
import 'reactflow/dist/style.css';
import { agenticApi } from '../api';
import { Search, Database } from 'lucide-react';
import { GlassCard, AnimatedButton, AISummaryPanel } from '../components/PremiumUI';
import { motion } from 'framer-motion';

const initialNodes = [
  {
    id: 'org',
    data: { label: '🏢 Organization: Acme' },
    position: { x: 250, y: 50 },
    style: { background: 'rgba(255, 255, 255, 0.95)', border: '1px solid rgba(0,0,0,0.06)', color: '#0f172a', fontSize: '11px', width: 160, borderRadius: '12px', fontWeight: 'bold' }
  },
  {
    id: 'wp',
    data: { label: '🎨 Site: wordpress.org' },
    position: { x: 100, y: 150 },
    style: { background: 'rgba(255, 255, 255, 0.95)', border: '1px solid rgba(0,0,0,0.06)', color: '#0f172a', fontSize: '11px', width: 160, borderRadius: '12px', fontWeight: 'bold' }
  },
  {
    id: 'c1',
    data: { label: '🕸 Crawl Job #104' },
    position: { x: 280, y: 250 },
    style: { background: 'rgba(255, 255, 255, 0.95)', border: '1px solid rgba(0,0,0,0.06)', color: '#0f172a', fontSize: '11px', width: 160, borderRadius: '12px', fontWeight: 'bold' }
  },
  {
    id: 'i1',
    data: { label: '⚠️ Issue: Broken Link' },
    position: { x: 420, y: 150 },
    style: { background: 'rgba(255, 255, 255, 0.95)', border: '1px solid rgba(0,0,0,0.06)', color: '#0f172a', fontSize: '11px', width: 160, borderRadius: '12px', fontWeight: 'bold' }
  }
];

const initialEdges = [
  { id: 'e1', source: 'org', target: 'wp', style: { stroke: '#6366f1', strokeWidth: 2.5 } },
  { id: 'e2', source: 'wp', target: 'c1', style: { stroke: '#6366f1', strokeWidth: 2.5 } },
  { id: 'e3', source: 'c1', target: 'i1', style: { stroke: '#6366f1', strokeWidth: 2.5 } },
];

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { type: "spring", stiffness: 350, damping: 25 } }
};

export default function KnowledgeGraphPage() {
  const [query, setQuery] = useState('');
  const [searchTriggered, setSearchTriggered] = useState(false);

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
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className="space-y-8"
    >
      <motion.div variants={itemVariants} className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight">Enterprise Knowledge Graph</h1>
          <p className="text-sm text-slate-500 font-semibold mt-1">Trace reasoning links, semantic facts, and entity structures discovered by autonomous agent scans</p>
        </div>
      </motion.div>

      {/* AI Summary Panel */}
      <motion.div variants={itemVariants}>
        <AISummaryPanel
          insights={[
            "Discovered semantic entity associations linking corporate organizations to sitemaps properties.",
            "Crawl logs trace execution anomalies back to structural page nodes automatically.",
            "Fact-retrieval indexes confirm perfect semantic coherence rating."
          ]}
          metrics={[
            { label: "Graph Density", value: "Optimal", trend: "4 key nodes mapped" },
            { label: "Fact Indexing Coherence", value: "98.6%", trend: "High accuracy facts link" }
          ]}
          thoughts={[
            "Loading index reasoning structures...",
            "Tracing parent-child node boundaries...",
            "Validating workspace anchor properties..."
          ]}
        />
      </motion.div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">
        {/* Search Panel */}
        <motion.div variants={itemVariants} className="xl:col-span-1">
          <GlassCard className="space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Database className="h-4.5 w-4.5 text-indigo-500" />
              <h2 className="text-sm font-bold text-slate-800">Semantic Search</h2>
            </div>

            <form onSubmit={handleSearch} className="space-y-3">
              <div className="relative">
                <Search className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
                <input
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setSearchTriggered(false); }}
                  placeholder="Query semantic memory..."
                  className="w-full bg-white/50 border border-slate-200 text-slate-800 text-xs pl-10 pr-4 py-2.5 rounded-xl focus:outline-none focus:border-indigo-500 font-semibold"
                />
              </div>
              <AnimatedButton type="submit" variant="primary" className="w-full py-3">
                Search Memory
              </AnimatedButton>
            </form>

            {/* Results list */}
            <div className="space-y-2 mt-4 overflow-y-auto max-h-[300px] scrollbar-thin">
              {isLoading && <div className="skeleton h-10 w-full" />}
              {searchTriggered && searchResults.length === 0 && !isLoading && (
                <p className="text-slate-400 text-[11px] text-center font-semibold">No matching entities found in memory.</p>
              )}
              {searchResults.map((item, idx) => (
                <div key={idx} className="p-3.5 bg-slate-50 border border-slate-100 rounded-xl">
                  <span className="text-xs font-bold text-slate-700 block leading-tight">{item.fact || item.label || JSON.stringify(item)}</span>
                </div>
              ))}
            </div>
          </GlassCard>
        </motion.div>

        {/* Visual Graph View */}
        <motion.div variants={itemVariants} className="xl:col-span-3 bg-white/60 border border-slate-200/80 rounded-2xl h-[500px] overflow-hidden relative shadow-md">
          <div className="absolute top-4 left-4 z-10 text-[10px] bg-white border border-slate-200 px-3 py-1.5 rounded-xl text-slate-600 font-bold shadow-sm">
            Reasoning Links Canvas
          </div>
          <ReactFlow
            nodes={initialNodes}
            edges={initialEdges}
            fitView
          >
            <Background color="rgba(99,102,241,0.06)" gap={16} />
            <Controls />
          </ReactFlow>
        </motion.div>
      </div>
    </motion.div>
  );
}
