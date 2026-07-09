import React, { useState } from 'react';
import {
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
  Outlet,
  Link,
  useLocation,
  useNavigate
} from '@tanstack/react-router';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { motion, AnimatePresence } from 'framer-motion';

/* ─── Pages ─── */
import DashboardPage from './pages/Dashboard';
import WorkspacePage from './pages/Workspace';
import SEOPage from './pages/SEO';
import CrawlerPage from './pages/Crawler';
import IssuesPage from './pages/Issues';
import FixesPage from './pages/Fixes';
import AutomationPage from './pages/Automation';
import AgenticPage from './pages/Agentic';
import KnowledgeGraphPage from './pages/KnowledgeGraph';
import AnalyticsPage from './pages/Analytics';
import CollaborationPage from './pages/Collaboration';
import MarketplacePage from './pages/Marketplace';
import EnterprisePage from './pages/Enterprise';
import BillingPage from './pages/Billing';
import SettingsPage from './pages/Settings';

/* ─── Components ─── */
import CommandPalette from './CommandPalette';
import AICopilotPanel from './AICopilotPanel';

import {
  LayoutDashboard,
  Layers,
  Search,
  AlertTriangle,
  Wrench,
  BarChart3,
  Play,
  Cpu,
  Database,
  Users2,
  Store,
  Building2,
  CreditCard,
  Settings,
  HelpCircle,
  Bell,
  ChevronDown
} from 'lucide-react';

/* ─── Root Route Shell ─── */
const rootRoute = createRootRoute({
  component: AppShell,
});

function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [showCmdPalette, setShowCmdPalette] = useState(false);
  const [showAiPanel, setShowAiPanel] = useState(false);
  const [selectedOrg, setSelectedOrg] = useState('Acme Corp');
  const [selectedWs, setSelectedWs] = useState('Production Site');

  const navItems = [
    { label: 'Dashboard', path: '/', icon: LayoutDashboard },
    { label: 'Workspace', path: '/workspace', icon: Layers },
    { label: 'SEO Diagnostics', path: '/seo', icon: HelpCircle },
    { label: 'Crawler Engine', path: '/crawler', icon: Play },
    { label: 'Issues Log', path: '/issues', icon: AlertTriangle },
    { label: 'AI Fixes', path: '/fixes', icon: Wrench },
    { label: 'Automation loops', path: '/automation', icon: Cpu },
    { label: 'Agentic AI Plan', path: '/agentic', icon: BrainCircuitIcon },
    { label: 'Knowledge Graph', path: '/knowledge-graph', icon: Database },
    { label: 'Analytics Panel', path: '/analytics', icon: BarChart3 },
    { label: 'Collaboration', path: '/collaboration', icon: Users2 },
    { label: 'Ecosystem Marketplace', path: '/marketplace', icon: Store },
    { label: 'Enterprise Admin', path: '/enterprise', icon: Building2 },
    { label: 'Billing Invoices', path: '/billing', icon: CreditCard },
    { label: 'System Settings', path: '/settings', icon: Settings },
  ];

  function BrainCircuitIcon(props: any) {
    return (
      <svg
        {...props}
        xmlns="http://www.w3.org/2000/svg"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1.27A7 7 0 0 1 14 22h-4a7 7 0 0 1-6.73-3H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z" />
      </svg>
    );
  }

  const currentPath = location.pathname;
  const currentLabel = navItems.find(n => n.path === currentPath)?.label || 'Console';

  return (
    <div className="app-shell">
      {/* ─── Persistent Sidebar ─── */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">W</div>
          <div className="flex flex-col">
            <span className="sidebar-brand-name">Orchestrator</span>
          </div>
          <span className="sidebar-brand-badge">SaaS</span>
        </div>

        {/* Switchers */}
        <div className="p-4 border-b border-slate-100 bg-white/40 space-y-2">
          {/* Org Switcher */}
          <DropdownMenu.Root>
            <DropdownMenu.Trigger className="w-full flex items-center justify-between bg-white border border-slate-200/80 rounded-xl px-3.5 py-2 text-xs text-slate-700 focus:outline-none shadow-sm hover:border-slate-300 transition-colors">
              <span className="font-bold truncate">{selectedOrg}</span>
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
            </DropdownMenu.Trigger>
            <DropdownMenu.Content className="bg-white/95 backdrop-blur-md border border-slate-200/80 rounded-xl p-1.5 shadow-lg min-w-[200px] z-50">
              <DropdownMenu.Item onClick={() => setSelectedOrg('Acme Corp')} className="text-xs font-semibold text-slate-700 hover:bg-indigo-50/80 hover:text-indigo-600 rounded-lg px-3 py-2.5 cursor-pointer outline-none transition-colors">Acme Corp</DropdownMenu.Item>
              <DropdownMenu.Item onClick={() => setSelectedOrg('Global Industries')} className="text-xs font-semibold text-slate-700 hover:bg-indigo-50/80 hover:text-indigo-600 rounded-lg px-3 py-2.5 cursor-pointer outline-none transition-colors">Global Industries</DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Root>

          {/* Workspace Switcher */}
          <DropdownMenu.Root>
            <DropdownMenu.Trigger className="w-full flex items-center justify-between bg-white border border-slate-200/80 rounded-xl px-3.5 py-2 text-xs text-slate-700 focus:outline-none shadow-sm hover:border-slate-300 transition-colors">
              <span className="font-bold truncate">{selectedWs}</span>
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
            </DropdownMenu.Trigger>
            <DropdownMenu.Content className="bg-white/95 backdrop-blur-md border border-slate-200/80 rounded-xl p-1.5 shadow-lg min-w-[200px] z-50">
              <DropdownMenu.Item onClick={() => setSelectedWs('Production Site')} className="text-xs font-semibold text-slate-700 hover:bg-indigo-50/80 hover:text-indigo-600 rounded-lg px-3 py-2.5 cursor-pointer outline-none transition-colors">Production Site</DropdownMenu.Item>
              <DropdownMenu.Item onClick={() => setSelectedWs('Staging Sandbox')} className="text-xs font-semibold text-slate-700 hover:bg-indigo-50/80 hover:text-indigo-600 rounded-lg px-3 py-2.5 cursor-pointer outline-none transition-colors">Staging Sandbox</DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Root>
        </div>

        {/* Navigation list */}
        <div className="flex-1 overflow-y-auto py-4 space-y-1.5 px-3 scrollbar-thin">
          {navItems.map((item) => {
            const isActive = currentPath === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`sidebar-link flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all ${
                  isActive ? 'bg-indigo-50/70 text-indigo-600 active' : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                <item.icon className="h-4.5 w-4.5" />
                {item.label}
              </Link>
            );
          })}
        </div>

        <div className="sidebar-footer">
          <button
            className="sidebar-link flex items-center justify-center gap-2 py-3 rounded-xl border border-indigo-100 hover:bg-indigo-50 transition-all cursor-pointer"
            onClick={() => setShowAiPanel(true)}
            style={{ width: '100%', background: 'rgba(99, 102, 241, 0.08)', color: '#6366f1' }}
          >
            <span className="font-extrabold text-xs">AI Copilot</span>
            <span className="sidebar-link-badge font-mono text-[9px] px-1.5 py-0.5 rounded bg-indigo-100/50">⌘J</span>
          </button>
        </div>
      </aside>

      {/* ─── Top Navigation & Search ─── */}
      <header className="topbar">
        <div className="topbar-breadcrumb">
          <span className="topbar-breadcrumb-item">Console</span>
          <span className="topbar-breadcrumb-sep">/</span>
          <span className="topbar-breadcrumb-item text-slate-800 font-bold">{currentLabel}</span>
        </div>

        <div className="topbar-search" onClick={() => setShowCmdPalette(true)}>
          <Search className="h-3.5 w-3.5 text-slate-400" />
          <span className="topbar-search-text font-medium">Search commands, workspaces...</span>
          <span className="topbar-search-kbd">⌘K</span>
        </div>

        <div className="topbar-actions">
          <button className="topbar-action-btn" onClick={() => setShowAiPanel(v => !v)}>
            <BrainCircuitIcon className="h-4.5 w-4.5 text-indigo-600" />
          </button>
          <button className="topbar-action-btn relative">
            <Bell className="h-4.5 w-4.5 text-slate-500" />
            <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 bg-indigo-600 rounded-full" />
          </button>
          <div className="topbar-avatar">SK</div>
        </div>
      </header>

      {/* ─── Main Content Outlet ─── */}
      <main className="main-content">
        <AnimatePresence mode="wait">
          <Outlet />
        </AnimatePresence>
      </main>

      {/* ─── Command Palette ─── */}
      {showCmdPalette && (
        <CommandPalette
          onClose={() => setShowCmdPalette(false)}
          onNavigate={(path) => { navigate({ to: path }); setShowCmdPalette(false); }}
        />
      )}

      {/* ─── AI Copilot side-drawer ─── */}
      {showAiPanel && <AICopilotPanel onClose={() => setShowAiPanel(false)} />}
    </div>
  );
}

/* ─── Routes Wiring ─── */
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: DashboardPage });
const workspaceRoute = createRoute({ getParentRoute: () => rootRoute, path: '/workspace', component: WorkspacePage });
const seoRoute = createRoute({ getParentRoute: () => rootRoute, path: '/seo', component: SEOPage });
const crawlerRoute = createRoute({ getParentRoute: () => rootRoute, path: '/crawler', component: CrawlerPage });
const issuesRoute = createRoute({ getParentRoute: () => rootRoute, path: '/issues', component: IssuesPage });
const fixesRoute = createRoute({ getParentRoute: () => rootRoute, path: '/fixes', component: FixesPage });
const automationRoute = createRoute({ getParentRoute: () => rootRoute, path: '/automation', component: AutomationPage });
const agenticRoute = createRoute({ getParentRoute: () => rootRoute, path: '/agentic', component: AgenticPage });
const graphRoute = createRoute({ getParentRoute: () => rootRoute, path: '/knowledge-graph', component: KnowledgeGraphPage });
const analyticsRoute = createRoute({ getParentRoute: () => rootRoute, path: '/analytics', component: AnalyticsPage });
const collabRoute = createRoute({ getParentRoute: () => rootRoute, path: '/collaboration', component: CollaborationPage });
const marketplaceRoute = createRoute({ getParentRoute: () => rootRoute, path: '/marketplace', component: MarketplacePage });
const enterpriseRoute = createRoute({ getParentRoute: () => rootRoute, path: '/enterprise', component: EnterprisePage });
const billingRoute = createRoute({ getParentRoute: () => rootRoute, path: '/billing', component: BillingPage });
const settingsRoute = createRoute({ getParentRoute: () => rootRoute, path: '/settings', component: SettingsPage });

const routeTree = rootRoute.addChildren([
  indexRoute,
  workspaceRoute,
  seoRoute,
  crawlerRoute,
  issuesRoute,
  fixesRoute,
  automationRoute,
  agenticRoute,
  graphRoute,
  analyticsRoute,
  collabRoute,
  marketplaceRoute,
  enterpriseRoute,
  billingRoute,
  settingsRoute,
]);

const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

export default function App() {
  return <RouterProvider router={router} />;
}
