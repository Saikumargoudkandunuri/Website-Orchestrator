import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coreApi, CrawlSummary, CrawlRequest } from '../api';
import { Play, RotateCcw, AlertCircle, FileText, CheckCircle2, History, ServerCrash } from 'lucide-react';

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
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-50 tracking-tight">Active Crawler Engine</h1>
          <p className="text-sm text-slate-400">Discover links, analyze source structures, detect errors, and check response headers</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Crawler Input Card */}
        <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl p-5 space-y-4 xl:col-span-1">
          <h2 className="text-sm font-semibold text-slate-200">Start Crawl Job</h2>
          <form onSubmit={handleStartCrawl} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Target Start URL</label>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                className="w-full bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Max Scanned Pages</label>
              <input
                type="number"
                min={1}
                max={500}
                value={maxPages}
                onChange={(e) => setMaxPages(Number(e.target.value))}
                className="w-24 bg-slate-950 border border-white/[0.08] text-xs px-3 py-2 rounded-lg focus:outline-none focus:border-violet-500 text-slate-100"
              />
            </div>

            <button
              type="submit"
              disabled={crawlMutation.isPending}
              className="w-full btn btn-primary flex justify-center items-center gap-1.5 py-2 text-xs"
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
            </button>
          </form>

          {/* Quick results if available */}
          {crawlMutation.data && (
            <div className="p-3 bg-emerald-950/20 border border-emerald-800/40 rounded-lg space-y-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">Job Complete</span>
              <div className="grid grid-cols-3 gap-2 text-center text-slate-200 mt-1">
                <div>
                  <div className="text-xs text-slate-400">Scanned</div>
                  <div className="text-sm font-bold">{crawlMutation.data.pages_crawled}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Issues</div>
                  <div className="text-sm font-bold text-rose-400">{crawlMutation.data.issues_found}</div>
                </div>
                <div>
                  <div className="text-xs text-slate-400">Fixes</div>
                  <div className="text-sm font-bold text-emerald-400">{crawlMutation.data.fixes_generated}</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Live console logging / queue output */}
        <div className="bg-slate-950/60 border border-white/[0.06] rounded-xl p-5 xl:col-span-2 flex flex-col h-[320px]">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs font-semibold text-slate-300">Live Engine Outputs</span>
            <button
              onClick={() => setCrawlLogs([])}
              className="text-[10px] text-slate-500 hover:text-slate-300 flex items-center gap-1"
            >
              <RotateCcw className="h-3 w-3" /> Clear Console
            </button>
          </div>

          <div className="flex-1 bg-black/40 border border-white/[0.03] p-4 rounded-lg font-mono text-[11px] text-slate-300 overflow-y-auto space-y-1.5 scrollbar-thin">
            {crawlLogs.length === 0 ? (
              <div className="text-slate-600 text-center py-20">
                Console idle. Submit a crawl job to view engine logs in real-time.
              </div>
            ) : (
              crawlLogs.map((log, i) => (
                <div key={i} className={log.startsWith('[ERROR]') ? 'text-rose-400' : log.includes('Success') || log.includes('complete') ? 'text-emerald-400' : 'text-slate-300'}>
                  {`[${new Date().toLocaleTimeString()}] ${log}`}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Crawl Run History list */}
      <div className="bg-slate-900/40 border border-white/[0.06] rounded-xl overflow-hidden">
        <div className="p-4 border-b border-white/[0.06]">
          <h2 className="text-sm font-semibold text-slate-200">Execution Runs Library</h2>
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
                <td className="mono text-xs text-slate-300">{h.url}</td>
                <td>
                  <span className={`badge ${h.status === 'Success' ? 'badge-success' : 'badge-error'}`}>
                    {h.status}
                  </span>
                </td>
                <td className="text-slate-100 font-semibold">{h.pages}</td>
                <td className="text-xs text-slate-500">{h.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
