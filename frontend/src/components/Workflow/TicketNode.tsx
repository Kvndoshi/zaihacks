import { Handle, Position } from '@xyflow/react';
import { cn } from '@/lib/utils';
import type { TicketDomain, TicketStatus } from '@/types/friction.types';

interface TicketNodeData {
  ticketId: string;
  label: string;
  domain: TicketDomain;
  status: TicketStatus;
  layer: number;
}

const STATUS_COLORS: Record<TicketStatus, string> = {
  blocked: 'border-gray-600',
  ready: 'border-friction-amber',
  in_progress: 'border-blue-500',
  completed: 'border-green-500',
  failed: 'border-friction-red',
};

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

export function TicketNode({ data }: { data: TicketNodeData }) {
  const { ticketId, label, domain, status } = data;

  return (
    <div
      className={cn(
        'bg-friction-surface rounded-lg border-2 px-3 py-2 min-w-[160px] max-w-[200px] cursor-pointer transition-all hover:scale-105',
        STATUS_COLORS[status],
        status === 'completed' && 'opacity-70',
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-friction-border !w-2 !h-2" />

      <div className="text-[10px] font-mono text-friction-muted">{ticketId}</div>
      <div className="text-xs font-medium text-gray-200 mt-0.5 leading-snug line-clamp-2">
        {label}
      </div>
      <div className="mt-1.5 flex items-center justify-between">
        <span className={cn('text-[9px] px-1.5 py-0.5 rounded-full font-medium', DOMAIN_COLORS[domain])}>
          {domain}
        </span>
        <span className={cn(
          'text-[9px] px-1.5 py-0.5 rounded-full',
          status === 'completed' ? 'bg-green-500/20 text-green-400' :
          status === 'in_progress' ? 'bg-blue-500/20 text-blue-400' :
          status === 'ready' ? 'bg-friction-amber/20 text-friction-amber' :
          'bg-gray-500/20 text-gray-500',
        )}>
          {status.replace('_', ' ')}
        </span>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-friction-border !w-2 !h-2" />
    </div>
  );
}
