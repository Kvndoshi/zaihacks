import { useMemo, useState } from 'react';
import { useFrictionStore } from '@/store/useFrictionStore';
import { TicketCard } from './TicketCard';
import { AgentPrompt } from './AgentPrompt';
import type { TicketDomain, TicketStatus } from '@/types/friction.types';

type GroupBy = 'layer' | 'issue';

export function TicketBoard() {
  const { tickets, toggleIssueGroupActive } = useFrictionStore();
  const [domainFilter, setDomainFilter] = useState<TicketDomain | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<TicketStatus | 'all'>('all');
  const [groupBy, setGroupBy] = useState<GroupBy>('layer');

  const filtered = useMemo(() => {
    let result = tickets;
    if (domainFilter !== 'all') result = result.filter((t) => t.domain === domainFilter);
    if (statusFilter !== 'all') result = result.filter((t) => t.status === statusFilter);
    return result;
  }, [tickets, domainFilter, statusFilter]);

  const hasIssueTickets = tickets.some((t) => t.source_issue_id);

  // Group by layer
  const layers = useMemo(() => {
    const grouped: Record<number, typeof tickets> = {};
    for (const t of filtered) {
      if (!grouped[t.layer]) grouped[t.layer] = [];
      grouped[t.layer].push(t);
    }
    return Object.entries(grouped)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([layer, items]) => ({ layer: Number(layer), tickets: items }));
  }, [filtered]);

  // Group by issue
  const issueGroups = useMemo(() => {
    const grouped: Record<string, { title: string; sourceIssueId: string; active: boolean; tickets: typeof tickets }> = {};
    const ungrouped: typeof tickets = [];

    for (const t of filtered) {
      if (t.source_issue_id && t.source_issue_title) {
        if (!grouped[t.source_issue_id]) {
          grouped[t.source_issue_id] = {
            title: t.source_issue_title,
            sourceIssueId: t.source_issue_id,
            active: t.active !== false,
            tickets: [],
          };
        }
        grouped[t.source_issue_id].tickets.push(t);
      } else {
        ungrouped.push(t);
      }
    }

    const groups = Object.values(grouped);
    if (ungrouped.length > 0) {
      groups.push({ title: 'Other Tickets', sourceIssueId: '', active: true, tickets: ungrouped });
    }
    return groups;
  }, [filtered]);

  const domains = [...new Set(tickets.map((t) => t.domain))];
  const stats = {
    total: tickets.length,
    completed: tickets.filter((t) => t.status === 'completed').length,
    inProgress: tickets.filter((t) => t.status === 'in_progress').length,
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Filter bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-friction-border bg-friction-darker/50 shrink-0">
        <span className="text-xs text-friction-muted">
          {stats.completed}/{stats.total} completed
          {stats.inProgress > 0 && ` | ${stats.inProgress} in progress`}
        </span>
        <AgentPrompt />
        <div className="flex-1" />
        {hasIssueTickets && (
          <select
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value as GroupBy)}
            className="text-xs bg-friction-surface border border-friction-border rounded px-2 py-1 text-gray-300"
          >
            <option value="layer">Group by Layer</option>
            <option value="issue">Group by Issue</option>
          </select>
        )}
        <select
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value as TicketDomain | 'all')}
          className="text-xs bg-friction-surface border border-friction-border rounded px-2 py-1 text-gray-300"
        >
          <option value="all">All domains</option>
          {domains.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as TicketStatus | 'all')}
          className="text-xs bg-friction-surface border border-friction-border rounded px-2 py-1 text-gray-300"
        >
          <option value="all">All statuses</option>
          <option value="blocked">Blocked</option>
          <option value="ready">Ready</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-x-auto overflow-y-auto p-4">
        {groupBy === 'layer' ? (
          <div className="flex gap-4 min-w-min">
            {layers.map(({ layer, tickets: layerTickets }) => (
              <div
                key={layer}
                className="w-72 shrink-0 bg-friction-darker/50 rounded-xl border border-friction-border"
              >
                <div className="px-3 py-2 border-b border-friction-border">
                  <h3 className="text-sm font-semibold text-gray-300">
                    Layer {layer}
                    <span className="ml-2 text-xs text-friction-muted font-normal">
                      ({layerTickets.length})
                    </span>
                  </h3>
                </div>
                <div className="p-2 space-y-2 max-h-[calc(100vh-240px)] overflow-y-auto">
                  {layerTickets.map((ticket) => (
                    <TicketCard key={ticket.id} ticket={ticket} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {issueGroups.map((group) => (
              <div
                key={group.sourceIssueId || 'other'}
                className={`bg-friction-darker/50 rounded-xl border border-friction-border ${
                  !group.active ? 'opacity-40' : ''
                }`}
              >
                <div className="flex items-center justify-between px-4 py-2 border-b border-friction-border">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-300">
                      {group.title}
                    </h3>
                    <span className="text-xs text-friction-muted">
                      ({group.tickets.length} tickets)
                    </span>
                    {!group.active && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-gray-500/20 text-gray-400 font-medium">
                        Paused
                      </span>
                    )}
                  </div>
                  {group.sourceIssueId && (
                    <button
                      onClick={() => toggleIssueGroupActive(group.sourceIssueId)}
                      className={`relative w-8 h-4 rounded-full transition-colors ${
                        group.active ? 'bg-friction-amber' : 'bg-gray-600'
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform ${
                          group.active ? 'left-4' : 'left-0.5'
                        }`}
                      />
                    </button>
                  )}
                </div>
                <div className="p-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {group.tickets.map((ticket) => (
                    <TicketCard key={ticket.id} ticket={ticket} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
