import { useFrictionStore } from '@/store/useFrictionStore';

export function StatusBar() {
  const { boardStats, tickets } = useFrictionStore();
  if (!boardStats) return null;

  const percent = boardStats.percent_complete;

  return (
    <div className="h-10 flex items-center gap-4 px-4 border-t border-friction-border bg-friction-darker/80 shrink-0">
      {/* Progress bar */}
      <div className="flex items-center gap-2 flex-1 max-w-xs">
        <div className="flex-1 h-2 bg-friction-surface rounded-full overflow-hidden">
          <div
            className="h-full bg-friction-amber rounded-full transition-all duration-500"
            style={{ width: `${percent}%` }}
          />
        </div>
        <span className="text-xs text-friction-muted whitespace-nowrap">
          {percent.toFixed(0)}%
        </span>
      </div>

      {/* Ticket counts */}
      <div className="flex gap-3 text-xs">
        <span className="text-green-400">{boardStats.completed} done</span>
        <span className="text-blue-400">{boardStats.in_progress} active</span>
        <span className="text-friction-amber">{boardStats.ready} ready</span>
        <span className="text-gray-500">{boardStats.blocked} blocked</span>
      </div>

      {/* Layer breakdown */}
      <div className="flex gap-2 text-xs text-friction-muted">
        {Object.entries(boardStats.layers || {})
          .sort(([a], [b]) => Number(a) - Number(b))
          .map(([layer, data]) => (
            <span key={layer}>
              L{layer}: {data.completed}/{data.total}
            </span>
          ))}
      </div>
    </div>
  );
}
