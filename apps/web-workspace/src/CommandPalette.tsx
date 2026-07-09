import React, { useState, useEffect, useRef } from 'react';

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
  { id: 'audit', label: 'Audit Trail', category: 'Navigation', path: '/audit-log' },
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
      <div className="command-palette" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          className="command-input"
          placeholder="Search commands, pages, actions…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <div className="command-list">
          {Object.entries(groups).map(([cat, items]) => (
            <div key={cat}>
              <div className="command-group-title">{cat}</div>
              {items.map((item) => {
                globalIdx++;
                const idx = globalIdx;
                return (
                  <div
                    key={item.id}
                    className={`command-item${idx === selectedIdx ? ' selected' : ''}`}
                    onClick={() => onNavigate(item.path)}
                    onMouseEnter={() => setSelectedIdx(idx)}
                  >
                    <span className="command-item-label">{item.label}</span>
                    {item.shortcut && <span className="command-item-shortcut">{item.shortcut}</span>}
                  </div>
                );
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
              No results for "{query}"
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
