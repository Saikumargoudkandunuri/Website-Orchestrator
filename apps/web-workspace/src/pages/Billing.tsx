import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { enterpriseApi } from '../api';
import { CreditCard, Check, RefreshCw } from 'lucide-react';
import { GlassCard, AnimatedButton, StatusBadge } from '../components/PremiumUI';
import { motion } from 'framer-motion';

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
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-8"
    >
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Billing & Subscriptions</h1>
          <p className="text-sm text-slate-500 mt-1">Review allocation usage counters, corporate tiers, and invoices logs</p>
        </div>
      </div>

      {/* Usage Counters */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[
          { key: 'crawl_pages_scanned', label: 'Crawl Scans Used', limit: '10,000' },
          { key: 'ai_optimizations_generated', label: 'AI Fixes Generated', limit: '1,000' },
          { key: 'automation_workflows_run', label: 'Workflows Executed', limit: '500' },
          { key: 'active_directory_users', label: 'Users Provisioned', limit: '50' },
        ].map((item) => {
          const val = usage[item.key] || 0;
          return (
            <GlassCard key={item.key} className="space-y-2">
              <span className="text-xs text-slate-400 font-bold uppercase tracking-widest block">{item.label}</span>
              <div className="text-2xl font-extrabold text-slate-900 mt-1">{val.toLocaleString()}</div>
              <p className="text-xs text-slate-400 font-semibold mt-1">Allocation Limit: {item.limit}</p>
            </GlassCard>
          );
        })}
      </div>

      {/* Subscription Plans Grid */}
      <div className="space-y-4">
        <h2 className="text-sm font-bold text-slate-800">Subscription Plans</h2>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {tiers.map((t) => (
            <div
              key={t.id}
              className={`bg-white/80 border rounded-2xl p-6 flex flex-col justify-between hover:border-indigo-400/50 transition-colors relative shadow-sm ${
                selectedPlan === t.id ? 'border-indigo-500 bg-white shadow-glow' : 'border-slate-200/80'
              }`}
            >
              {selectedPlan === t.id && (
                <span className="absolute top-0 right-0 transform translate-x-[-12px] translate-y-[-10px] bg-indigo-600 text-[9px] uppercase font-bold px-2 py-0.5 rounded-full text-white">
                  Current Tier
                </span>
              )}

              <div className="space-y-4">
                <div>
                  <h3 className="text-base font-bold text-slate-800">{t.name}</h3>
                  <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">{t.desc}</p>
                </div>

                <div className="flex items-baseline gap-1.5 border-b border-slate-100 pb-4">
                  <span className="text-3xl font-extrabold text-slate-900">{t.price}</span>
                  <span className="text-xs text-slate-400 font-semibold">/ month</span>
                </div>

                <ul className="space-y-2 text-xs text-slate-600 font-medium">
                  {t.features.map((f, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-indigo-500 flex-shrink-0" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <AnimatedButton
                onClick={() => { setSelectedPlan(t.id); handleSubscribe(t.id); }}
                variant={selectedPlan === t.id ? 'primary' : 'secondary'}
                className="w-full mt-6 py-2.5"
              >
                {selectedPlan === t.id ? 'Active Plan' : 'Upgrade Subscription'}
              </AnimatedButton>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
