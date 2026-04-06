import { Flame, Wifi, WifiOff } from 'lucide-react';
import { useFrictionStore } from '@/store/useFrictionStore';
import type { ActiveView } from '@/store/useFrictionStore';
import { cn } from '@/lib/utils';

interface HeaderProps {
  connected: boolean;
}

export function Header({ connected }: HeaderProps) {
  const { activeView, setActiveView, tickets, activeSession, boardStats } = useFrictionStore();

  const { githubIssues } = useFrictionStore();

  const tabs: { key: ActiveView; label: string; show: boolean }[] = [
    { key: 'deliberation', label: 'Deliberation', show: true },
    { key: 'issues', label: `Issues${githubIssues.length ? ` (${githubIssues.length})` : ''}`, show: githubIssues.length > 0 },
    { key: 'tickets', label: 'Tickets', show: tickets.length > 0 },
    { key: 'workflow', label: 'Workflow', show: tickets.length > 0 },
  ];

  const phase = activeSession?.status === 'deliberating'
    ? 'Deliberating'
    : activeSession?.status === 'completed'
    ? 'Completed'
    : null;

  return (
    <header className="h-12 flex items-center justify-between px-4 border-b border-friction-border bg-friction-darker/80 backdrop-blur-sm shrink-0">
      <div className="flex items-center gap-3">
        <Flame className="w-5 h-5 text-friction-amber" />
        <span className="font-bold text-lg tracking-wider amber-glow">FRICTION</span>
        <span className="text-xs text-friction-muted hidden sm:inline">
          The AI that debates your idea first
        </span>
      </div>

      <div className="flex items-center gap-1">
        {tabs.filter(t => t.show).map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveView(tab.key)}
            className={cn(
              'px-3 py-1 text-sm rounded-md transition-colors',
              activeView === tab.key
                ? 'bg-friction-amber/20 text-friction-amber'
                : 'text-gray-400 hover:text-gray-200 hover:bg-friction-surface',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-3">
        {phase && (
          <span className={cn(
            'text-xs px-2 py-0.5 rounded-full',
            activeSession?.status === 'deliberating'
              ? 'bg-friction-amber/20 text-friction-amber'
              : 'bg-green-500/20 text-green-400',
          )}>
            {phase}
          </span>
        )}
        {boardStats && (
          <span className="text-xs text-friction-muted">
            {boardStats.completed}/{boardStats.total} tickets
          </span>
        )}
        {connected ? (
          <Wifi className="w-4 h-4 text-green-500" />
        ) : (
          <WifiOff className="w-4 h-4 text-friction-red" />
        )}
      </div>
    </header>
  );
}
