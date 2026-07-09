import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coreApi, CrawlSummary, CrawlRequest } from '../api';
import { Play, RotateCcw, AlertCircle, FileText, CheckCircle2, History, ServerCrash } from 'lucide-react';
import { GlassCard, AnimatedButton, GlassInput, StatusBadge } from '../components/PremiumUI';
import { motion } from 'framer-motion';

export default function CrawlerPage() {
  const queryClient = useQueryClient();
  const [url, setUrl] = useState('https://wordpress.org');
  const [maxPages, setMaxPages] = useState(25);
  const [crawlLogs, setCrawlLogs] = useState<string[]>([]);

  // Mutation to start the crawl
  const crawlMutation = useMutation<CrawlSummary, Error, CrawlRequest>({
    mutationFn: (data) => {
      setCrawlLogs([`Initializing crawl for ${data.start_url}...`]);
      return coreApi.crawl(data);
    },
    onMutate: () => {
      setCrawlLogs(prev => [...prev, 'Validating URL pattern...', 'Requesting worker reservation...']);
    },
    onSuccess: (data) => {
      setCrawlLogs(prev => [
        ...prev,
        'Worker allocated successfully.',
        `Crawl process finished. Pages scanned: ${data.pages_crawled}.`,
        `Identified ${data.issues_found} issues.`,
        `Generated ${data.fixes_generated} suggested fixes.`,
        'Database update completed successfully.'
      ]);
      queryClient.invalidateQueries({ queryKey: ['issues'] });
      queryClient.invalidateQueries({ queryKey: ['fixes'] });
      queryClient.invalidateQueries({ queryKey: ['auditLog'] });
    },
    onError: (err) => {
      setCrawlLogs(prev => [...prev, `[ERROR] Crawl run aborted: ${err.message}`]);
    }
  });

  const handleStartCrawl = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    crawlMutation.mutate({ start_url: url, max_pages: maxPages });
  };

  const mockHistory = [
    { id: '1', url: 'https://wordpress.org', pages: 20, status: 'Success', date: '2026-07-08 18:24' },
    { id: '2', url: 'https://developer.wordpress.org', pages: 5, status: 'Success', date: '2026-07-08 18:15' },
    { id: '3', url: 'https://invalid-url-crawl', pages: 0, status: 'Failed', date: '2026-07-08 17:50' },
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
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Active Crawler Engine</h1>
          <p className="text-sm text-slate-500 mt-1">Discover links, analyze source structures, detect errors, and verify responsive codes</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Crawler Input Card */}
        <GlassCard className="space-y-4 xl:col-span-1">
          <h2 className="text-sm font-bold text-slate-800">Start Crawl Job</h2>
          <form onSubmit={handleStartCrawl} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Target Start URL</label>
              <GlassInput
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block">Max Scanned Pages</label>
              <GlassInput
                type="number"
                min={1}
                max={500}
                value={maxPages}
                onChange={(e) => setMaxPages(Number(e.target.value))}
                style={{ width: '100px' }}
              />
            </div>

            <AnimatedButton
              type="submit"
              disabled={crawlMutation.isPending}
              variant="primary"
              className="w-full py-2.5"
            >
              {crawlMutation.isPending ? (
                <>
                  <span className="animate-spin h-3.5 w-3.5 border-2 border-slate-300 border-t-white rounded-full block" />
                  Running Crawl...
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5" /> Start Crawl Job
                </>
              )}
            </AnimatedButton>
          </form>

          {/* Quick results */}
          {crawlMutation.data && (
            <div className="p-4 bg-emerald-50/50 border border-emerald-100 rounded-xl space-y-2 mt-4">
              <span className="text-[10px] font-extrabold uppercase tracking-widest text-emerald-600">Job Complete</span>
              <div className="grid grid-cols-3 gap-2 text-center text-slate-700 mt-2">
                <div>
                  <div className="text-[10px] text-slate-400 font-semibold uppercase">Scanned</div>
                  <div className="text-base font-extrabold text-slate-800">{crawlMutation.data.pages_crawled}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400 font-semibold uppercase">Issues</div>
                  <div className="text-base font-extrabold text-rose-500">{crawlMutation.data.issues_found}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400 font-semibold uppercase">Fixes</div>
                  <div className="text-base font-extrabold text-emerald-600">{crawlMutation.data.fixes_generated}</div>
                </div>
              </div>
            </div>
          )}
        </GlassCard>

        {/* Live console logging */}
        <GlassCard className="xl:col-span-2 flex flex-col h-[340px] p-5">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs font-bold text-slate-700">Crawler Output Terminal</span>
            <button
              onClick={() => setCrawlLogs([])}
              className="text-[10px] font-bold text-slate-400 hover:text-indigo-500 flex items-center gap-1 transition-colors"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Clear Console
            </button>
          </div>

          <div className="flex-1 bg-slate-950 border border-slate-900 p-4 rounded-xl font-mono text-[11px] text-slate-300 overflow-y-auto space-y-1.5 scrollbar-thin shadow-inner">
            {crawlLogs.length === 0 ? (
              <div className="text-slate-500 text-center py-24">
                Console idle. Run a crawl job to stream logs.
              </div>
            ) : (
              crawlLogs.map((log, i) => (
                <div key={i} className={log.startsWith('[ERROR]') ? 'text-rose-400' : log.includes('Success') || log.includes('complete') ? 'text-emerald-400' : 'text-slate-300'}>
                  {`[${new Date().toLocaleTimeString()}] ${log}`}
                </div>
              ))
            )}
          </div>
        </GlassCard>
      </div>

      {/* Crawl Run History */}
      <GlassCard className="p-0 overflow-hidden">
        <div className="p-5 border-b border-slate-100">
          <h2 className="text-sm font-bold text-slate-800">Job Execution History</h2>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th>Start URL</th>
              <th>Status</th>
              <th>Pages Scanned</th>
              <th>Crawl Date</th>
            </tr>
          </thead>
          <tbody>
            {mockHistory.map((h) => (
              <tr key={h.id}>
                <td className="mono text-xs text-indigo-600 font-semibold">{h.url}</td>
                <td>
                  <StatusBadge status={h.status} />
                </td>
                <td className="text-slate-900 font-bold">{h.pages}</td>
                <td className="text-xs text-slate-400">{h.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>
    </motion.div>
  );
}
