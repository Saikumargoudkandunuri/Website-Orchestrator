import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { marketplaceApi } from '../api';
import { Plus, Link2 } from 'lucide-react';
import { GlassCard, AnimatedButton, GlassInput, StatusBadge } from '../components/PremiumUI';
import { motion } from 'framer-motion';

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
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-8"
    >
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Ecosystem Marketplace</h1>
          <p className="text-sm text-slate-500 mt-1">Discover integrations or register custom web plugins</p>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab${activeTab === 'available' ? ' active' : ''}`} onClick={() => setActiveTab('available')}>Available Plugins</button>
        <button className={`tab${activeTab === 'developer' ? ' active' : ''}`} onClick={() => setActiveTab('developer')}>Developer Integration</button>
      </div>

      {activeTab === 'available' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {isLoading ? (
            <div className="skeleton h-44 w-full" />
          ) : apps.length === 0 ? (
            [
              { id: 'wp-sync', name: 'WordPress Core Sync', desc: 'Sync generated SEO optimization fixes directly onto target WP installs.', installed: true },
              { id: 'slack-bot', name: 'Slack Alerts Bot', desc: 'Post crawlers diagnostics outputs and pending fixes directly to Slack.', installed: false },
              { id: 'google-search', name: 'Google Search Console Connect', desc: 'Pull keyword query positions and crawl statistics directly from GSC.', installed: false },
            ].map((item) => (
              <GlassCard key={item.id} className="flex flex-col justify-between hover:border-indigo-400/50 transition-colors">
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <h3 className="text-sm font-bold text-slate-800">{item.name}</h3>
                    {item.installed && <span className="text-[9px] font-extrabold uppercase tracking-wider text-emerald-600 bg-emerald-50 border border-emerald-100/50 px-2 py-0.5 rounded-md">Active</span>}
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed mt-2">{item.desc}</p>
                </div>
                
                {!item.installed && (
                  <AnimatedButton
                    onClick={() => handleInstallApp(item.id)}
                    variant="primary"
                    className="w-full mt-6 py-2.5"
                  >
                    <Link2 className="h-4 w-4" /> Install Integration
                  </AnimatedButton>
                )}
              </GlassCard>
            ))
          ) : (
            apps.map((app, i) => (
              <GlassCard key={i} className="flex flex-col justify-between hover:border-indigo-400/50 transition-colors">
                <div className="space-y-2">
                  <h3 className="text-sm font-bold text-slate-800">{app.name || app.app_name}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed mt-2">{app.description || 'Custom developer integration'}</p>
                </div>
                <AnimatedButton
                  onClick={() => handleInstallApp(app.id || `app-${i}`)}
                  variant="primary"
                  className="w-full mt-6 py-2.5"
                >
                  <Link2 className="h-4 w-4" /> Install Integration
                </AnimatedButton>
              </GlassCard>
            ))
          )}
        </div>
      )}

      {activeTab === 'developer' && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Register App */}
          <GlassCard className="space-y-4 xl:col-span-1">
            <h2 className="text-sm font-bold text-slate-800">Register Developer App</h2>
            <form onSubmit={handleRegisterApp} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">App Name</label>
                <GlassInput
                  value={appName}
                  onChange={(e) => setAppName(e.target.value)}
                  placeholder="e.g. Analytics Exporter"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Redirect URI (OAuth)</label>
                <GlassInput
                  value={appUrl}
                  onChange={(e) => setAppUrl(e.target.value)}
                  placeholder="https://myplugin.com/callback"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Description</label>
                <GlassInput
                  value={appDesc}
                  onChange={(e) => setAppDesc(e.target.value)}
                  placeholder="Explain your app scopes..."
                />
              </div>

              <AnimatedButton
                type="submit"
                disabled={registerMutation.isPending}
                variant="primary"
                className="w-full py-2.5"
              >
                <Plus className="h-4 w-4" /> Save App Credentials
              </AnimatedButton>
            </form>
          </GlassCard>

          {/* Client Details */}
          <GlassCard className="xl:col-span-2 p-5">
            <h2 className="text-sm font-bold text-slate-800 mb-3">OAuth Client Credentials</h2>
            <div className="bg-slate-950 border border-slate-900 p-4 rounded-xl font-mono text-[11px] text-slate-400 space-y-3 shadow-inner">
              <div>
                <span className="text-slate-500 font-semibold uppercase">CLIENT_ID:</span>
                <p className="text-slate-300 mt-1 select-all">orchestrator_client_dev_showcase_key_1042</p>
              </div>
              <div>
                <span className="text-slate-500 font-semibold uppercase">CLIENT_SECRET:</span>
                <p className="text-slate-300 mt-1 select-all">••••••••••••••••••••••••••••••••••••••••</p>
              </div>
              <div className="text-[10px] text-amber-500 mt-4 font-semibold">
                ⚠️ Store credentials securely. Do not share OAuth secrets.
              </div>
            </div>
          </GlassCard>
        </div>
      )}
    </motion.div>
  );
}
