import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { X, CheckCircle2, Circle, FileCode, GitBranch, User, Clock } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useFrictionStore } from '@/store/useFrictionStore';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { Ticket } from '@/types/friction.types';

export function TicketDetail() {
  const { selectedTicketId, selectTicket, tickets } = useFrictionStore();
  const [depOutputs, setDepOutputs] = useState<Record<string, string>>({});
  const [ticket, setTicket] = useState<Ticket | null>(null);

  useEffect(() => {
    if (!selectedTicketId) return;
    const t = tickets.find((t) => t.id === selectedTicketId);
    if (t) setTicket(t);

    api.getTicketContext(selectedTicketId).then((ctx) => {
      setDepOutputs(ctx.dependency_outputs);
    }).catch(() => {});
  }, [selectedTicketId, tickets]);

  if (!ticket) return null;

  const STATUS_LABEL: Record<string, { text: string; className: string }> = {
    blocked: { text: 'Blocked', className: 'bg-gray-500/20 text-gray-400' },
    ready: { text: 'Ready', className: 'bg-friction-amber/20 text-friction-amber' },
    in_progress: { text: 'In Progress', className: 'bg-blue-500/20 text-blue-400' },
    completed: { text: 'Completed', className: 'bg-green-500/20 text-green-400' },
    failed: { text: 'Failed', className: 'bg-red-500/20 text-red-400' },
  };

  const statusInfo = STATUS_LABEL[ticket.status] || STATUS_LABEL.blocked;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-start justify-end bg-black/50"
      onClick={() => selectTicket(null)}
    >
      <motion.div
        initial={{ x: 400 }}
        animate={{ x: 0 }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="w-[520px] h-full bg-friction-darker border-l border-friction-border overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-friction-darker border-b border-friction-border px-5 py-3 flex items-center justify-between z-10">
          <div>
            <span className="text-xs font-mono text-friction-muted">{ticket.id}</span>
            <h2 className="text-lg font-semibold text-gray-200">{ticket.title}</h2>
          </div>
          <button onClick={() => selectTicket(null)} className="text-gray-400 hover:text-gray-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Meta badges */}
          <div className="flex flex-wrap gap-2">
            <span className={cn('text-xs px-2 py-0.5 rounded-full', statusInfo.className)}>
              {statusInfo.text}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-friction-surface text-gray-400">
              Layer {ticket.layer}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-friction-surface text-gray-400">
              {ticket.domain}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-friction-surface text-gray-400">
              Priority: {['Critical', 'High', 'Medium', 'Low'][ticket.priority]}
            </span>
          </div>

          {/* Agent */}
          {ticket.agent_id && (
            <div className="flex items-center gap-2 text-sm text-blue-400">
              <User className="w-4 h-4" />
              Claimed by {ticket.agent_id}
              {ticket.claimed_at && (
                <span className="text-friction-muted ml-2 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(ticket.claimed_at).toLocaleTimeString()}
                </span>
              )}
            </div>
          )}

          {/* Description */}
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Description</h3>
            <div className="prose prose-sm prose-invert max-w-none text-gray-300 bg-friction-surface rounded-lg p-3 border border-friction-border">
              <ReactMarkdown>{ticket.description}</ReactMarkdown>
            </div>
          </div>

          {/* Acceptance criteria */}
          {ticket.acceptance_criteria.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Acceptance Criteria
              </h3>
              <ul className="space-y-1.5">
                {ticket.acceptance_criteria.map((ac, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                    {ticket.status === 'completed' ? (
                      <CheckCircle2 className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                    ) : (
                      <Circle className="w-4 h-4 text-gray-500 mt-0.5 shrink-0" />
                    )}
                    {ac}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Files */}
          {(ticket.files_to_create.length > 0 || ticket.files_to_modify.length > 0) && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Files</h3>
              {ticket.files_to_create.length > 0 && (
                <div className="mb-2">
                  <span className="text-[10px] text-green-400 uppercase">Create:</span>
                  {ticket.files_to_create.map((f) => (
                    <div key={f} className="flex items-center gap-1.5 text-sm text-gray-300 ml-2">
                      <FileCode className="w-3 h-3 text-green-400" />
                      <code className="text-xs">{f}</code>
                    </div>
                  ))}
                </div>
              )}
              {ticket.files_to_modify.length > 0 && (
                <div>
                  <span className="text-[10px] text-yellow-400 uppercase">Modify:</span>
                  {ticket.files_to_modify.map((f) => (
                    <div key={f} className="flex items-center gap-1.5 text-sm text-gray-300 ml-2">
                      <FileCode className="w-3 h-3 text-yellow-400" />
                      <code className="text-xs">{f}</code>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Dependencies */}
          {ticket.depends_on.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Dependencies
              </h3>
              {ticket.depends_on.map((depId) => (
                <div key={depId} className="mb-2">
                  <div className="flex items-center gap-1.5 text-sm">
                    <GitBranch className="w-3 h-3 text-friction-muted" />
                    <span className="font-mono text-xs text-friction-amber">{depId}</span>
                  </div>
                  {depOutputs[depId] && (
                    <div className="mt-1 ml-5 text-xs text-gray-400 bg-friction-surface/50 rounded p-2 border border-friction-border/50">
                      {depOutputs[depId]}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Output summary */}
          {ticket.output_summary && (
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Output Summary
              </h3>
              <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-3 text-sm text-gray-300">
                {ticket.output_summary}
              </div>
            </div>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
