import { useFrictionStore } from '@/store/useFrictionStore';

const EVENT_LABELS: Record<string, string> = {
  session_created: 'Session created',
  session_message: 'Message',
  deliberation_complete: 'Deliberation complete',
  tickets_generated: 'Tickets generated',
  ticket_claimed: 'Ticket claimed',
  ticket_completed: 'Ticket completed',
  ticket_failed: 'Ticket failed',
  workflow_update: 'Workflow updated',
  agent_connected: 'Agent connected',
  agent_disconnected: 'Agent disconnected',
  status_update: 'Status updated',
};

export function EventFeed() {
  const events = useFrictionStore((s) => s.events);

  if (events.length === 0) return null;

  const recent = events.slice(-8);

  return (
    <div className="h-7 flex items-center gap-4 px-4 border-t border-friction-border/50 bg-friction-darker overflow-hidden shrink-0">
      <span className="text-[10px] text-friction-muted uppercase tracking-wider shrink-0">Live</span>
      <div className="flex gap-4 overflow-x-auto scrollbar-hide">
        {recent.map((event, i) => (
          <span key={i} className="text-[11px] text-friction-amber/70 whitespace-nowrap shrink-0">
            {EVENT_LABELS[event.type] || event.type}
            {event.data?.ticket_id ? (
              <span className="text-friction-muted ml-1">{String(event.data.ticket_id)}</span>
            ) : null}
          </span>
        ))}
      </div>
    </div>
  );
}
