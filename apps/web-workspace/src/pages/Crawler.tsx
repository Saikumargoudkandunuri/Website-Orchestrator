import React, { useState } from 'react';
import { coreApi, type CrawlSummary } from '../api';

export default function CrawlerPage() {
  const [url, setUrl] = useState('');
  const [maxPages, setMaxPages] = useState(50);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CrawlSummary | null>(null);
  const [error, setError] = useState('');

  const handleCrawl = async () => {
    if (!url.trim()) { setError('Please enter a URL'); return; }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const summary = await coreApi.crawl({ start_url: url, max_pages: maxPages });
      setResult(summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Crawl failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Crawler</h1>
          <p>Crawl websites to detect SEO issues, broken links, and performance problems</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: '640px' }}>
        <div className="card-header">
          <div className="card-title">New Crawl</div>
        </div>
        <div className="card-body">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Target URL
              </label>
              <input
                className="input"
                placeholder="https://example.com"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Max Pages
              </label>
              <input
                className="input"
                type="number"
                min="1"
                max="1000"
                value={maxPages}
                onChange={(e) => setMaxPages(Number(e.target.value))}
                style={{ maxWidth: '120px' }}
              />
            </div>

            {error && (
              <div style={{ padding: '10px 14px', background: 'var(--error-bg)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--error)', fontSize: '13px' }}>
                {error}
              </div>
            )}

            <button className="btn btn-primary" onClick={handleCrawl} disabled={loading} style={{ alignSelf: 'flex-start' }}>
              {loading ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="animate-spin" style={{ display: 'inline-block', width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%' }} />
                  Crawling…
                </span>
              ) : 'Start Crawl'}
            </button>
          </div>
        </div>
      </div>

      {result && (
        <div style={{ marginTop: '20px' }}>
          <div className="stats-grid" style={{ maxWidth: '640px' }}>
            <div className="stat-card">
              <div className="stat-card-label">Pages Crawled</div>
              <div className="stat-card-value">{result.pages_crawled}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Issues Found</div>
              <div className="stat-card-value">{result.issues_found}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Fixes Generated</div>
              <div className="stat-card-value">{result.fixes_generated}</div>
            </div>
          </div>
          <div style={{ marginTop: '12px', padding: '12px 16px', background: 'var(--success-bg)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 'var(--radius-md)', color: 'var(--success)', fontSize: '13px', maxWidth: '640px' }}>
            ✓ Crawl complete. View results in Issues and Fixes pages.
          </div>
        </div>
      )}
    </div>
  );
}
