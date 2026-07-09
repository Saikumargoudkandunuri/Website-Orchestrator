import React, { useState, useRef, useEffect } from 'react';
import { copilotApi } from './api';

interface Props {
  onClose: () => void;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function AICopilotPanel({ onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: 'Hello! I\'m your AI Copilot. Ask me about your website health, crawl results, SEO issues, or anything else. I can help you navigate the platform, explain fixes, and provide insights.' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const response = await copilotApi.chat(userMsg);
      setMessages((prev) => [...prev, { role: 'assistant', content: response.reply || response.response || JSON.stringify(response) }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `I encountered an issue connecting to the backend. Please ensure the API server is running. Error: ${err instanceof Error ? err.message : 'Unknown error'}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-panel">
      <div className="ai-panel-header">
        <div className="ai-panel-title">
          <span className="ai-dot" />
          AI Copilot
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
      </div>

      <div className="ai-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`ai-message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
        {loading && (
          <div className="ai-message assistant" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="ai-dot" /> Thinking…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="ai-input-bar">
        <input
          className="ai-input"
          placeholder="Ask the AI Copilot…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') sendMessage(); }}
        />
        <button className="btn btn-primary btn-sm" onClick={sendMessage} disabled={loading}>
          Send
        </button>
      </div>
    </div>
  );
}
