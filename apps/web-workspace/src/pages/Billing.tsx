import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { enterpriseApi } from '../api';
import { CreditCard, Check, ShieldAlert, Sparkles, Receipt, RefreshCw } from 'lucide-react';

export default function BillingPage() {
  const queryClient = useQueryClient();
  const [selectedPlan, setSelectedPlan] = useState('enterprise');
  
  // Queries
  const { data: usage = {}, isLoading: loadingUsage } = useQuery<Record<string, number>>({
    queryKey: ['billingUsage'],
    queryFn: enterpriseApi.getUsage,
  });

  // Mutations
  const subscribeMutation = useMutation({
    mutationFn: (data: { plan: string; billing_cycle: string }) =>
      enterpriseApi.createSubscription('demo-org', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billingUsage'] });
      alert('Subscription tier updated successfully!');
    }
  });

  const handleSubscribe = (plan: string) => {
    subscribeMutation.mutate({ plan, billing_cycle: 'monthly' });
  };

  const tiers = [
    { id: 'starter', name: 'Starter Pro', price: '$49', desc: 'Ideal for single site optimization audits.', features: ['Up to 50 pages crawl', 'AI optimization recommendations', 'Weekly automated diagnostics'] },
    { id: 'business', name: 'Business Scale', price: '$199', desc: 'For growing web properties and brands.', features: ['Up to 500 pages crawl', 'Automated code fixes', 'Daily quality checks', 'SCIM Directory integration'] },
    { id: 'enterprise', name: 'Corporate Enterprise', price: '$499', desc: 'Custom governance models and scaling.', features: ['Unlimited crawl scans', 'Direct git workflow publish', 'Full compliance audit trail', 'Priority model response guarantees'] },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">Billing & Subscriptions</h1>
          <p className="text-sm text-slate-400">Establish corporate tiers, inspect billing invoices, and review resource usage counters</p>
        </div>
      </div>

      {/* Usage Counters */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { key: 'crawl_pages_scanned', label: 'Crawl Scans Used', limit: '10,000' },
          { key: 'ai_optimizations_generated', label: 'AI Fixes Generated', limit: '1,000' },
          { key: 'automation_workflows_run', label: 'Workflows Executed', limit: '500' },
          { key: 'active_directory_users', label: 'Users Provisioned', limit: '50' },
        ].map((item) => {
          const val = usage[item.key] || 0;
          return (
            <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-2" key={item.key}>
              <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">{item.label}</span>
              <div className="text-2xl font-bold text-slate-100 mt-1">{val.toLocaleString()}</div>
              <p className="text-xs text-slate-500">Allocation Limit: {item.limit}</p>
            </div>
          );
        })}
      </div>

      {/* Subscription Plans Grid */}
      <div className="space-y-4">
        <h2 className="text-sm font-semibold text-slate-200">Subscription Plans</h2>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {tiers.map((t) => (
            <div
              key={t.id}
              className={`bg-slate-900/40 border rounded-xl p-6 flex flex-col justify-between hover:border-violet-500/45 transition-colors relative ${
                selectedPlan === t.id ? 'border-violet-500 bg-slate-900/60 shadow-glow' : 'border-white/[0.06]'
              }`}
            >
              {selectedPlan === t.id && (
                <span className="absolute top-0 right-0 transform translate-x-[-12px] translate-y-[-10px] bg-violet-600 text-[9px] uppercase font-bold px-2 py-0.5 rounded-full text-white">
                  Current Tier
                </span>
              )}

              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-bold text-slate-100">{t.name}</h3>
                  <p className="text-xs text-slate-400 mt-1.5">{t.desc}</p>
                </div>

                <div className="flex items-baseline gap-1.5 border-b border-white/[0.04] pb-4">
                  <span className="text-3xl font-extrabold text-slate-50">{t.price}</span>
                  <span className="text-xs text-slate-400">/ month</span>
                </div>

                <ul className="space-y-2 text-xs text-slate-300">
                  {t.features.map((f, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <Check className="h-3.5 w-3.5 text-violet-400 flex-shrink-0" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <button
                onClick={() => { setSelectedPlan(t.id); handleSubscribe(t.id); }}
                className={`w-full btn mt-6 py-2 text-xs font-semibold ${selectedPlan === t.id ? 'btn-primary' : 'btn-secondary'}`}
              >
                {selectedPlan === t.id ? 'Active Plan' : 'Upgrade Subscription'}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
