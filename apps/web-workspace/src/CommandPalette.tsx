import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Search } from 'lucide-react';

interface Props {
  onClose: () => void;
  onNavigate: (path: string) => void;
}

interface CmdItem {
  id: string;
  label: string;
  category: string;
  path: string;
  shortcut?: string;
}

const COMMANDS: CmdItem[] = [
  { id: 'dash', label: 'Go to Dashboard', category: 'Navigation', path: '/', shortcut: '⌘1' },
  { id: 'ws', label: 'Go to Workspace', category: 'Navigation', path: '/workspace', shortcut: '⌘2' },
  { id: 'crawl', label: 'Start New Crawl', category: 'Actions', path: '/crawler' },
  { id: 'issues', label: 'View Issues', category: 'Navigation', path: '/issues' },
  { id: 'fixes', label: 'Review Fixes', category: 'Navigation', path: '/fixes' },
  { id: 'analytics', label: 'View Analytics', category: 'Navigation', path: '/analytics' },
  { id: 'auto', label: 'Create Workflow', category: 'Actions', path: '/automation' },
  { id: 'agentic', label: 'Agentic AI Console', category: 'AI', path: '/agentic' },
  { id: 'collab', label: 'Collaboration Hub', category: 'Navigation', path: '/collaboration' },
  { id: 'market', label: 'Marketplace', category: 'Navigation', path: '/marketplace' },
  { id: 'enterprise', label: 'Enterprise Admin', category: 'Navigation', path: '/enterprise' },
  { id: 'settings', label: 'Settings', category: 'Navigation', path: '/settings' },
];

export default function CommandPalette({ onClose, onNavigate }: Props) {
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = COMMANDS.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase()) ||
    c.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => { setSelectedIdx(0); }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIdx((i) => Math.min(i + 1, filtered.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIdx((i) => Math.max(i - 1, 0)); }
    else if (e.key === 'Enter' && filtered[selectedIdx]) { onNavigate(filtered[selectedIdx].path); }
    else if (e.key === 'Escape') { onClose(); }
  };

  // Group by category
  const groups: Record<string, CmdItem[]> = {};
  filtered.forEach((c) => {
    if (!groups[c.category]) groups[c.category] = [];
    groups[c.category].push(c);
  });

  let globalIdx = -1;

  return (
    <div className="command-overlay" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: -20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.97, y: -20 }}
        transition={{ type: "spring", stiffness: 400, damping: 28 }}
        className="w-full max-w-xl bg-white/95 backdrop-blur-3xl border border-slate-200/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col p-2"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative flex items-center border-b border-slate-100 px-4 py-3">
          <Search className="h-4.5 w-4.5 text-slate-400 mr-3" />
          <input
            ref={inputRef}
            className="w-full bg-transparent text-slate-800 text-sm focus:outline-none placeholder:text-slate-400 font-semibold"
            placeholder="Search commands, pages, actions…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>

        <div className="overflow-y-auto max-h-[300px] py-2 scrollbar-thin">
          {Object.entries(groups).map(([cat, items]) => (
            <div key={cat}>
              <div className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest px-4 py-2">{cat}</div>
              {items.map((item) => {
                globalIdx++;
                const idx = globalIdx;
                return (
                  <div
                    key={item.id}
                    className={`flex items-center justify-between px-4 py-2.5 mx-2 rounded-xl text-xs font-bold cursor-pointer transition-colors ${
                      idx === selectedIdx ? 'bg-indigo-50/80 text-indigo-600' : 'text-slate-600 hover:bg-slate-50'
                    }`}
                    onClick={() => onNavigate(item.path)}
                    onMouseEnter={() => setSelectedIdx(idx)}
                  >
                    <span>{item.label}</span>
                    {item.shortcut && (
                      <span className="font-mono text-[10px] text-slate-400 bg-slate-100 border border-slate-200/50 px-1.5 py-0.5 rounded-md">
                        {item.shortcut}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="py-12 text-center text-slate-400 text-xs font-medium">
              No results for "{query}"
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
