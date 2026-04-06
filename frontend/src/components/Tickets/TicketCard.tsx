import { useState } from 'react';
import { cn } from '@/lib/utils';
import { useFrictionStore } from '@/store/useFrictionStore';
import type { Ticket, TicketDomain } from '@/types/friction.types';
import { User, Trash2, Pencil, Send, X, CheckCircle2, Circle } from 'lucide-react';

const DOMAIN_COLORS: Record<TicketDomain, string> = {
  backend: 'bg-blue-500/20 text-blue-400',
  frontend: 'bg-purple-500/20 text-purple-400',
  database: 'bg-emerald-500/20 text-emerald-400',
  auth: 'bg-red-500/20 text-red-400',
  api: 'bg-cyan-500/20 text-cyan-400',
  testing: 'bg-yellow-500/20 text-yellow-400',
  infra: 'bg-orange-500/20 text-orange-400',
  docs: 'bg-gray-500/20 text-gray-400',
  marketing: 'bg-pink-500/20 text-pink-400',
  design: 'bg-violet-500/20 text-violet-400',
  research: 'bg-teal-500/20 text-teal-400',
  operations: 'bg-amber-500/20 text-amber-400',
  content: 'bg-indigo-500/20 text-indigo-400',
  legal: 'bg-slate-500/20 text-slate-400',
  business: 'bg-lime-500/20 text-lime-400',
  general: 'bg-neutral-500/20 text-neutral-400',
};

const PRIORITY_DOT: Record<number, string> = {
  0: 'bg-red-500',
  1: 'bg-orange-500',
  2: 'bg-yellow-500',
  3: 'bg-gray-500',
};

const STATUS_BG: Record<string, string> = {
  blocked: 'border-l-gray-600',
  ready: 'border-l-friction-amber',
  in_progress: 'border-l-blue-500',
  completed: 'border-l-green-500',
  failed: 'border-l-friction-red',
};

interface TicketCardProps {
  ticket: Ticket;
}

export function TicketCard({ ticket }: TicketCardProps) {
  const selectTicket = useFrictionStore((s) => s.selectTicket);
  const deleteTicketAction = useFrictionStore((s) => s.deleteTicket);
  const modifyTicketAction = useFrictionStore((s) => s.modifyTicket);
  const toggleTicketComplete = useFrictionStore((s) => s.toggleTicketComplete);

  const [isModifying, setIsModifying] = useState(false);
  const [modifyInput, setModifyInput] = useState('');

  const handleToggleComplete = (e: React.MouseEvent) => {
    e.stopPropagation();
    toggleTicketComplete(ticket.id);
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    deleteTicketAction(ticket.id);
  };

  const handleModifyToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsModifying(!isModifying);
    setModifyInput('');
  };

  const handleModifySubmit = (e: React.MouseEvent | React.FormEvent) => {
    e.stopPropagation();
    if (!modifyInput.trim()) return;
    modifyTicketAction(ticket.id, modifyInput.trim());
    setIsModifying(false);
    setModifyInput('');
  };

  return (
    <div
      onClick={() => selectTicket(ticket.id)}
      className={cn(
        'group bg-friction-surface rounded-lg border border-friction-border border-l-2 p-3 cursor-pointer hover:border-friction-border/80 transition-all hover:translate-y-[-1px] hover:shadow-lg',
        STATUS_BG[ticket.status],
        ticket.status === 'completed' && 'opacity-60',
        ticket.active === false && 'opacity-40',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleToggleComplete}
            className={cn(
              'shrink-0 transition-colors',
              ticket.status === 'completed'
                ? 'text-green-400 hover:text-green-300'
                : 'text-gray-500 hover:text-gray-300'
            )}
            title={ticket.status === 'completed' ? 'Mark as not completed' : 'Mark as completed'}
          >
            {ticket.status === 'completed' ? (
              <CheckCircle2 className="w-3.5 h-3.5" />
            ) : (
              <Circle className="w-3.5 h-3.5" />
            )}
          </button>
          <span className="text-[10px] font-mono text-friction-muted">{ticket.id}</span>
        </div>
        <span className={cn('w-2 h-2 rounded-full shrink-0 mt-1', PRIORITY_DOT[ticket.priority])} />
      </div>

      {ticket.source_issue_title && (
        <span className="text-[9px] text-friction-amber/70 font-mono mt-0.5 block truncate">
          Issue {ticket.source_issue_title}
        </span>
      )}

      <h4 className={cn(
        'text-xs font-medium mt-1 leading-snug line-clamp-2',
        ticket.status === 'completed' ? 'text-gray-400 line-through' : 'text-gray-200'
      )}>
        {ticket.title}
      </h4>

      {isModifying && (
        <div className="mt-2 flex gap-1" onClick={(e) => e.stopPropagation()}>
          <input
            type="text"
            value={modifyInput}
            onChange={(e) => setModifyInput(e.target.value)}
            placeholder="Describe changes..."
            className="flex-1 bg-friction-dark border border-friction-border rounded px-2 py-1 text-[10px] text-gray-200 placeholder:text-gray-500 focus:outline-none focus:border-friction-amber/50"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleModifySubmit(e);
              if (e.key === 'Escape') { setIsModifying(false); setModifyInput(''); }
            }}
          />
          <button onClick={handleModifySubmit} className="p-1 rounded bg-friction-amber/20 text-friction-amber hover:bg-friction-amber/30">
            <Send className="w-3 h-3" />
          </button>
          <button onClick={handleModifyToggle} className="p-1 rounded text-gray-500 hover:text-gray-300">
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      <div className="flex items-center justify-between mt-2">
        <span className={cn('text-[9px] px-1.5 py-0.5 rounded-full font-medium', DOMAIN_COLORS[ticket.domain])}>
          {ticket.domain}
        </span>

        <div className="flex items-center gap-1">
          {ticket.agent_id && (
            <span className="flex items-center gap-1 text-[10px] text-blue-400">
              <User className="w-3 h-3" />
              {ticket.agent_id.slice(0, 8)}
            </span>
          )}
          <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={handleModifyToggle}
              className="p-1 rounded text-friction-amber/60 hover:text-friction-amber hover:bg-friction-amber/10"
              title="Modify ticket"
            >
              <Pencil className="w-3 h-3" />
            </button>
            <button
              onClick={handleDelete}
              className="p-1 rounded text-red-400/60 hover:text-red-400 hover:bg-red-400/10"
              title="Delete ticket"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
