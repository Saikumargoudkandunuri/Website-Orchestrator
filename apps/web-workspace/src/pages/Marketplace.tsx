import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { marketplaceApi } from '../api';
import { AppWindow, Settings, LayoutGrid, Plus, Globe, Check, Link2 } from 'lucide-react';

export default function MarketplacePage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'available' | 'developer'>('available');
  
  // Developer Registration States
  const [appName, setAppName] = useState('');
  const [appUrl, setAppUrl] = useState('');
  const [appDesc, setAppDesc] = useState('');

  // Queries
  const { data: apps = [], isLoading } = useQuery<any[]>({
    queryKey: ['marketplaceApps'],
    queryFn: marketplaceApi.listApps,
  });

  // Mutations
  const registerMutation = useMutation({
    mutationFn: (data: any) => marketplaceApi.registerApp('dev-user', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplaceApps'] });
      setAppName('');
      setAppUrl('');
      setAppDesc('');
      alert('Developer App registered successfully!');
    }
  });

  const installMutation = useMutation({
    mutationFn: (appId: string) => marketplaceApi.installApp({ app_id: appId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplaceApps'] });
      alert('Application installed successfully!');
    }
  });

  const handleRegisterApp = (e: React.FormEvent) => {
    e.preventDefault();
    if (!appName.trim() || !appUrl.trim()) return;
    registerMutation.mutate({
      name: appName,
      description: appDesc,
      redirect_uri: appUrl,
      scopes: ['read', 'write']
    });
  };

  const handleInstallApp = (appId: string) => {
    installMutation.mutate(appId);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">Ecosystem Marketplace</h1>
          <p className="text-sm text-slate-400">Discover and install platform integrations or publish custom web plugins</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'available' ? ' active' : ''}`} onClick={() => setActiveTab('available')}>Available Plugins</button>
        <button className={`tab${activeTab === 'developer' ? ' active' : ''}`} onClick={() => setActiveTab('developer')}>Developer Integration</button>
      </div>

      {activeTab === 'available' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {isLoading ? (
              <div className="skeleton h-44 w-full" />
            ) : apps.length === 0 ? (
              // Default showcase plugins
              [
                { id: 'wp-sync', name: 'WordPress Core Sync', desc: 'Sync generated SEO optimization fixes directly onto target WP installs.', installed: true },
                { id: 'slack-bot', name: 'Slack Alerts Bot', desc: 'Post crawlers diagnostics outputs and pending fixes directly to Slack.', installed: false },
                { id: 'google-search', name: 'Google Search Console Connect', desc: 'Pull keyword query positions and crawl statistics directly from GSC.', installed: false },
              ].map((item) => (
                <div key={item.id} className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 flex flex-col justify-between hover:border-violet-500/40 transition-colors">
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <h3 className="text-sm font-semibold text-slate-200">{item.name}</h3>
                      {item.installed && <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800/30">Active</span>}
                    </div>
                    <p className="text-xs text-slate-400 mt-2">{item.desc}</p>
                  </div>
                  
                  {!item.installed && (
                    <button
                      onClick={() => handleInstallApp(item.id)}
                      className="w-full btn btn-primary flex justify-center items-center gap-1.5 mt-6 py-2 text-xs"
                    >
                      <Link2 className="h-4 w-4" /> Install Integration
                    </button>
                  )}
                </div>
              ))
            ) : (
              apps.map((app, i) => (
                <div key={i} className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 flex flex-col justify-between hover:border-violet-500/40 transition-colors">
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-slate-200">{app.name || app.app_name}</h3>
                    <p className="text-xs text-slate-400 mt-2">{app.description || 'Custom developer integration'}</p>
                  </div>
                  <button
                    onClick={() => handleInstallApp(app.id || `app-${i}`)}
                    className="w-full btn btn-primary flex justify-center items-center gap-1.5 mt-6 py-2 text-xs"
                  >
                    <Link2 className="h-4 w-4" /> Install Integration
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {activeTab === 'developer' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {/* Register App */}
          <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 xl:col-span-1">
            <h2 className="text-sm font-semibold text-slate-200">Register Developer App</h2>
            <form onSubmit={handleRegisterApp} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">App Name</label>
                <input
                  value={appName}
                  onChange={(e) => setAppName(e.target.value)}
                  placeholder="e.g. Analytics Exporter"
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Redirect URI (OAuth)</label>
                <input
                  value={appUrl}
                  onChange={(e) => setAppUrl(e.target.value)}
                  placeholder="https://myplugin.com/callback"
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Description</label>
                <input
                  value={appDesc}
                  onChange={(e) => setAppDesc(e.target.value)}
                  placeholder="Explain your app scopes..."
                  className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100 placeholder:text-slate-600"
                />
              </div>

              <button
                type="submit"
                disabled={registerMutation.isPending}
                className="w-full btn btn-primary flex justify-center items-center gap-1.5 py-2 text-xs"
              >
                <Plus className="h-4 w-4" /> Save App Credentials
              </button>
            </form>
          </div>

          {/* Client Details */}
          <div className="bg-slate-950/60 border border-white/[0.06] rounded-xl p-5 xl:col-span-2">
            <h2 className="text-sm font-semibold text-slate-200 mb-3">OAuth Client Credentials</h2>
            <div className="bg-black/40 border border-white/[0.03] p-4 rounded-lg font-mono text-[11px] text-slate-400 h-60 space-y-3">
              <div>
                <span className="text-slate-500">CLIENT_ID:</span>
                <p className="text-slate-300 mt-1 select-all">orchestrator_client_dev_showcase_key_1042</p>
              </div>
              <div>
                <span className="text-slate-500">CLIENT_SECRET:</span>
                <p className="text-slate-300 mt-1 select-all">••••••••••••••••••••••••••••••••••••••••</p>
              </div>
              <div className="text-[10px] text-amber-500 mt-4 flex items-center gap-1">
                ⚠️ Store credentials securely. Do not share OAuth secrets.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
