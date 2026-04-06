import { useState, useEffect } from 'react';
import { useFrictionStore } from '@/store/useFrictionStore';
import { api } from '@/lib/api';
import { Copy, Check, Terminal, X } from 'lucide-react';

export function AgentPrompt() {
  const { activeSessionId, showAgentPrompt, setShowAgentPrompt } = useFrictionStore();
  const [prompt, setPrompt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [show, setShow] = useState(false);

  // Auto-show when store flag is set (after ticket generation)
  useEffect(() => {
    if (showAgentPrompt && activeSessionId && !show) {
      setShowAgentPrompt(false);
      loadPrompt();
    }
  }, [showAgentPrompt, activeSessionId]);

  const loadPrompt = async () => {
    if (!activeSessionId) return;
    setLoading(true);
    try {
      const data = await api.getAgentPrompt(activeSessionId);
      setPrompt(data.prompt);
      setShow(true);
    } catch {
      setPrompt(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!prompt) return;
    await navigator.clipboard.writeText(prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleClose = () => {
    setShow(false);
  };

  if (!show) {
    return (
      <button
        onClick={loadPrompt}
        disabled={loading}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-friction-amber/10 text-friction-amber hover:bg-friction-amber/20 transition-colors text-xs font-medium"
      >
        <Terminal className="w-3.5 h-3.5" />
        {loading ? 'Loading...' : 'Agent Prompt'}
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={handleClose}>
      <div
        className="bg-friction-darker border border-friction-border rounded-xl w-[700px] max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-friction-border">
          <h2 className="text-sm font-semibold text-gray-200 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-friction-amber" />
            Agent Prompt — Copy into Claude Code or Cursor
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-friction-amber text-black font-medium text-xs hover:bg-friction-amber/90 transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied!' : 'Copy Prompt'}
            </button>
            <button onClick={handleClose} className="text-gray-400 hover:text-gray-200">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          <pre className="text-xs text-gray-300 whitespace-pre-wrap font-mono leading-relaxed">
            {prompt}
          </pre>
        </div>

        <div className="px-5 py-3 border-t border-friction-border text-[10px] text-friction-muted">
          Paste this prompt into Claude Code or Cursor with the Friction MCP server connected.
          The agent will automatically claim tickets, implement them, and report progress.
        </div>
      </div>
    </div>
  );
}
