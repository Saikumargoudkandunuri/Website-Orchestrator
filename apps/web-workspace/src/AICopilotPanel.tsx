import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { copilotApi } from './api';
import { X, Send, Cpu, Sparkles } from 'lucide-react';
import { GlassInput, AnimatedButton } from './components/PremiumUI';

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
    <motion.div
      initial={{ x: 420, opacity: 0.9 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 420, opacity: 0.9 }}
      transition={{ type: "spring", stiffness: 350, damping: 30 }}
      className="fixed right-0 top-0 bottom-0 w-[420px] bg-white/95 backdrop-blur-3xl border-l border-slate-200/80 z-50 flex flex-col shadow-2xl p-0"
    >
      {/* Header */}
      <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-white/50">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-indigo-50 text-indigo-600 rounded-lg">
            <Sparkles className="h-4.5 w-4.5" />
          </div>
          <span className="font-extrabold text-sm text-slate-800 tracking-tight">AI Copilot Chat</span>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 p-1.5 hover:bg-slate-100/80 rounded-lg transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
        {messages.map((msg, i) => {
          const isUser = msg.role === 'user';
          return (
            <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
              <div className={`p-3.5 max-w-[85%] rounded-2xl text-xs leading-relaxed font-medium shadow-sm ${
                isUser ? 'bg-indigo-600 text-white rounded-br-none' : 'bg-slate-100 text-slate-700 rounded-bl-none'
              }`}>
                {msg.content}
              </div>
            </div>
          );
        })}
        {loading && (
          <div className="flex justify-start">
            <div className="p-3.5 bg-slate-100 text-slate-500 rounded-2xl rounded-bl-none text-xs flex items-center gap-2.5 shadow-sm font-semibold">
              <span className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
              Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="p-4 border-t border-slate-100 bg-white/50 flex gap-2">
        <GlassInput
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the AI Copilot..."
          onKeyDown={(e) => { if (e.key === 'Enter') sendMessage(); }}
        />
        <AnimatedButton
          onClick={sendMessage}
          disabled={loading}
          variant="primary"
          className="px-4"
        >
          <Send className="h-3.5 w-3.5" />
        </AnimatedButton>
      </div>
    </motion.div>
  );
}
