import React, { useState, useEffect, useCallback } from 'react';
import { Routes, Route, useNavigate, useLocation, Link } from 'react-router-dom';

/* ─── Pages ─── */
import DashboardPage from './pages/Dashboard';
import CrawlerPage from './pages/Crawler';
import IssuesPage from './pages/Issues';
import FixesPage from './pages/Fixes';
import AuditLogPage from './pages/AuditLog';
import AnalyticsPage from './pages/Analytics';
import AutomationPage from './pages/Automation';
import AgenticPage from './pages/Agentic';
import WorkspacePage from './pages/Workspace';
import CollaborationPage from './pages/Collaboration';
import MarketplacePage from './pages/Marketplace';
import EnterprisePage from './pages/Enterprise';
import SettingsPage from './pages/Settings';

/* ─── Components ─── */
import CommandPalette from './CommandPalette';
import AICopilotPanel from './AICopilotPanel';

/* ─── SVG Icons (inline for zero-dep) ─── */
const Icon = ({ d, size = 18 }: { d: string; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

const icons = {
  dashboard: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10",
  crawler: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M2 12h20 M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z",
  issues: "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01",
  fixes: "M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z",
  audit: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
  analytics: "M18 20V10 M12 20V4 M6 20v-6",
  automation: "M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2",
  agentic: "M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5",
  workspace: "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z",
  collab: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2 M9 7a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M23 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",
  marketplace: "M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z M3 6h18 M16 10a4 4 0 0 1-8 0",
  enterprise: "M3 21h18 M5 21V7l8-4v18 M19 21V11l-6-4 M9 9h1 M9 13h1 M9 17h1",
  settings: "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  ai: "M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1.27A7 7 0 0 1 14 22h-4a7 7 0 0 1-6.73-3H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z M10 17a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M14 17a1 1 0 1 0 0-2 1 1 0 0 0 0 2z",
  search: "M11 17.25a6.25 6.25 0 1 1 0-12.5 6.25 6.25 0 0 1 0 12.5z M16 16l4.5 4.5",
  bell: "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9 M13.73 21a2 2 0 0 1-3.46 0",
  chevron: "M9 18l6-6-6-6",
};

interface NavItem {
  id: string;
  label: string;
  icon: string;
  path: string;
  badge?: string;
}

const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: 'Overview',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: 'dashboard', path: '/' },
      { id: 'workspace', label: 'Workspace', icon: 'workspace', path: '/workspace' },
    ],
  },
  {
    title: 'Intelligence',
    items: [
      { id: 'crawler', label: 'Crawler', icon: 'crawler', path: '/crawler' },
      { id: 'issues', label: 'Issues', icon: 'issues', path: '/issues' },
      { id: 'fixes', label: 'Fixes', icon: 'fixes', path: '/fixes' },
      { id: 'analytics', label: 'Analytics', icon: 'analytics', path: '/analytics' },
    ],
  },
  {
    title: 'Automation',
    items: [
      { id: 'automation', label: 'Workflows', icon: 'automation', path: '/automation' },
      { id: 'agentic', label: 'Agentic AI', icon: 'agentic', path: '/agentic', badge: 'AI' },
    ],
  },
  {
    title: 'Platform',
    items: [
      { id: 'collab', label: 'Collaboration', icon: 'collab', path: '/collaboration' },
      { id: 'marketplace', label: 'Marketplace', icon: 'marketplace', path: '/marketplace' },
      { id: 'enterprise', label: 'Enterprise', icon: 'enterprise', path: '/enterprise' },
      { id: 'audit', label: 'Audit Trail', icon: 'audit', path: '/audit-log' },
      { id: 'settings', label: 'Settings', icon: 'settings', path: '/settings' },
    ],
  },
];

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [showCmdPalette, setShowCmdPalette] = useState(false);
  const [showAiPanel, setShowAiPanel] = useState(false);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      setShowCmdPalette((v) => !v);
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'j') {
      e.preventDefault();
      setShowAiPanel((v) => !v);
    }
    if (e.key === 'Escape') {
      setShowCmdPalette(false);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const currentPageLabel = (() => {
    for (const section of NAV_SECTIONS) {
      for (const item of section.items) {
        if (location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path))) {
          return item.label;
        }
      }
    }
    return 'Dashboard';
  })();

  return (
    <div className="app-shell">
      {/* ─── Sidebar ─── */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">W</div>
          <div>
            <div className="sidebar-brand-name">Orchestrator</div>
          </div>
          <span className="sidebar-brand-badge">Pro</span>
        </div>

        {NAV_SECTIONS.map((section) => (
          <div className="sidebar-section" key={section.title}>
            <div className="sidebar-section-title">{section.title}</div>
            <nav className="sidebar-nav">
              {section.items.map((item) => {
                const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
                return (
                  <Link
                    key={item.id}
                    to={item.path}
                    className={`sidebar-link${isActive ? ' active' : ''}`}
                  >
                    <span className="sidebar-link-icon">
                      <Icon d={icons[item.icon as keyof typeof icons] || icons.dashboard} />
                    </span>
                    {item.label}
                    {item.badge && <span className="sidebar-link-badge">{item.badge}</span>}
                  </Link>
                );
              })}
            </nav>
          </div>
        ))}

        <div className="sidebar-footer">
          <button
            className="sidebar-link"
            onClick={() => setShowAiPanel(true)}
            style={{ width: '100%', border: 'none', background: 'var(--accent-glow)', cursor: 'pointer', fontFamily: 'var(--font-family)' }}
          >
            <span className="sidebar-link-icon"><Icon d={icons.ai} /></span>
            AI Copilot
            <span className="sidebar-link-badge">⌘J</span>
          </button>
        </div>
      </aside>

      {/* ─── Topbar ─── */}
      <header className="topbar">
        <div className="topbar-breadcrumb">
          <span className="topbar-breadcrumb-item">Console</span>
          <span className="topbar-breadcrumb-sep">/</span>
          <span className="topbar-breadcrumb-item" style={{ color: 'var(--text-primary)' }}>{currentPageLabel}</span>
        </div>

        <div className="topbar-search" onClick={() => setShowCmdPalette(true)}>
          <span style={{ color: 'var(--text-muted)', display: 'flex' }}>
            <Icon d={icons.search} size={14} />
          </span>
          <span className="topbar-search-text">Search or command…</span>
          <span className="topbar-search-kbd">⌘K</span>
        </div>

        <div className="topbar-actions">
          <button className="topbar-action-btn" onClick={() => setShowAiPanel((v) => !v)}>
            <Icon d={icons.ai} size={16} />
          </button>
          <button className="topbar-action-btn">
            <Icon d={icons.bell} size={16} />
          </button>
          <div className="topbar-avatar">SK</div>
        </div>
      </header>

      {/* ─── Main Content ─── */}
      <main className="main-content">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/crawler" element={<CrawlerPage />} />
          <Route path="/issues" element={<IssuesPage />} />
          <Route path="/fixes" element={<FixesPage />} />
          <Route path="/audit-log" element={<AuditLogPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/automation" element={<AutomationPage />} />
          <Route path="/agentic" element={<AgenticPage />} />
          <Route path="/collaboration" element={<CollaborationPage />} />
          <Route path="/marketplace" element={<MarketplacePage />} />
          <Route path="/enterprise" element={<EnterprisePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>

      {/* ─── Command Palette ─── */}
      {showCmdPalette && (
        <CommandPalette
          onClose={() => setShowCmdPalette(false)}
          onNavigate={(path) => { navigate(path); setShowCmdPalette(false); }}
        />
      )}

      {/* ─── AI Copilot Panel ─── */}
      {showAiPanel && <AICopilotPanel onClose={() => setShowAiPanel(false)} />}
    </div>
  );
}
