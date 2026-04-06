import { useState, useRef, useEffect } from 'react';
import { Send, CheckCircle, Loader2, Sparkles } from 'lucide-react';
import { useFrictionStore } from '@/store/useFrictionStore';
import { MessageBubble } from './MessageBubble';
import { ConfidenceSlider } from './ConfidenceSlider';

export function DeliberationChat() {
  const {
    messages,
    activeSession,
    isSending,
    isGeneratingTickets,
    sendMessage,
    completeDeliberation,
    refineTickets,
  } = useFrictionStore();

  const [input, setInput] = useState('');
  const [showConfidence, setShowConfidence] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const isDeliberating = activeSession?.status === 'deliberating';
  const isCompleted = activeSession?.status === 'completed';
  const canComplete = isDeliberating && messages.length >= 2;

  const handleSend = async () => {
    if (!input.trim() || isSending) return;
    const text = input;
    setInput('');
    if (isCompleted) {
      await refineTickets(text);
    } else {
      await sendMessage(text);
    }
  };

  const handleConfidenceSubmit = async (scores: Record<string, number>) => {
    setShowConfidence(false);
    await sendMessage(
      `My confidence ratings: ${Object.entries(scores).map(([k, v]) => `${k}: ${v}/10`).join(', ')}`,
      scores,
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isSending && (
          <div className="flex items-center gap-2 text-friction-muted text-sm pl-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            {isCompleted ? 'Refining tickets...' : 'Friction is thinking...'}
          </div>
        )}
        {isGeneratingTickets && (
          <div className="flex items-center gap-2 text-friction-amber text-sm pl-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            Generating tickets from deliberation...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Confidence slider */}
      {showConfidence && (
        <ConfidenceSlider onSubmit={handleConfidenceSubmit} onCancel={() => setShowConfidence(false)} />
      )}

      {/* Input bar — show during deliberation AND after completion */}
      {(isDeliberating || isCompleted) && (
        <div className="border-t border-friction-border p-3">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={isCompleted ? 'Describe changes to your tickets...' : 'Respond to Friction...'}
              className="flex-1 bg-friction-surface border border-friction-border rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-500 resize-none focus:outline-none focus:border-friction-amber/50"
              rows={2}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
            />
            <div className="flex flex-col gap-1">
              <button
                onClick={handleSend}
                disabled={!input.trim() || isSending}
                className="p-2 rounded-lg bg-friction-amber text-black hover:bg-friction-amber/90 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                {isCompleted ? <Sparkles className="w-4 h-4" /> : <Send className="w-4 h-4" />}
              </button>
              {isDeliberating && (
                <button
                  onClick={() => setShowConfidence(true)}
                  className="p-2 rounded-lg text-xs text-friction-muted hover:bg-friction-surface"
                  title="Rate your confidence"
                >
                  1-10
                </button>
              )}
            </div>
          </div>
          {canComplete && isDeliberating && (
            <button
              onClick={completeDeliberation}
              disabled={isGeneratingTickets}
              className="mt-2 w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-friction-amber text-black font-medium hover:bg-friction-amber/90 transition-colors text-sm"
            >
              <CheckCircle className="w-4 h-4" />
              Generate Tickets
              <span className="text-xs opacity-70 ml-1">Skip remaining phases</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
