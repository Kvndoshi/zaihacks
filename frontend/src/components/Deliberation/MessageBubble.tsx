import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';
import type { SessionMessage } from '@/types/friction.types';

interface MessageBubbleProps {
  message: SessionMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isFriction = message.role === 'friction';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn('flex', isUser ? 'justify-end' : 'justify-start')}
    >
      <div
        className={cn(
          'max-w-[85%] rounded-xl px-4 py-3 text-sm',
          isUser
            ? 'bg-friction-amber/15 border border-friction-amber/30 text-gray-200'
            : 'bg-friction-surface border border-friction-border text-gray-300',
        )}
      >
        {isFriction && (message.phase || message.web_searched) && (
          <div className="mb-2 flex items-center gap-2">
            {message.phase && (
              <span className="text-[10px] uppercase tracking-wider font-semibold text-friction-red/70 bg-friction-red/10 px-2 py-0.5 rounded-full">
                {message.phase.replace('_', ' ')}
              </span>
            )}
            {message.web_searched && (
              <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-semibold text-blue-400/80 bg-blue-500/10 px-2 py-0.5 rounded-full">
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="2" y1="12" x2="22" y2="12" />
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                </svg>
                Searched the web
              </span>
            )}
          </div>
        )}

        <div className="prose prose-sm prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4 [&_p]:my-1.5 [&_li]:my-0.5 [&_code]:bg-black/30 [&_code]:px-1 [&_code]:rounded">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>

        {message.confidence_score != null && (
          <div className="mt-2 text-xs text-friction-muted">
            Confidence: {message.confidence_score.toFixed(1)}/10
          </div>
        )}
      </div>
    </motion.div>
  );
}
