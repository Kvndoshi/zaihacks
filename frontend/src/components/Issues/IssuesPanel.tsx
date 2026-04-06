import { useMemo, useState } from 'react';
import { useFrictionStore } from '@/store/useFrictionStore';
import { IssueCard } from './IssueCard';
import type { IssueType } from '@/types/friction.types';
import { Loader2 } from 'lucide-react';

export function IssuesPanel() {
  const {
    githubIssues,
    selectedIssueIds,
    isGeneratingIssueTickets,
    toggleIssueSelection,
    selectAllIssues,
    deselectAllIssues,
    generateTicketsFromIssues,
  } = useFrictionStore();

  const [typeFilter, setTypeFilter] = useState<IssueType | 'all'>('all');

  const filtered = useMemo(() => {
    if (typeFilter === 'all') return githubIssues;
    return githubIssues.filter((i) => i.issue_type === typeFilter);
  }, [githubIssues, typeFilter]);

  const allSelected = filtered.length > 0 && filtered.every((i) => selectedIssueIds.includes(i.id));

  const handleSelectAll = () => {
    if (allSelected) {
      deselectAllIssues();
    } else {
      selectAllIssues();
    }
  };

  if (githubIssues.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-friction-muted">
        <p className="text-sm">No GitHub issues found for this repository.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Filter bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-friction-border bg-friction-darker/50 shrink-0">
        <label className="flex items-center gap-1.5 text-xs text-friction-muted cursor-pointer">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={handleSelectAll}
            className="accent-[#f59e0b]"
          />
          Select all
        </label>
        <span className="text-xs text-friction-muted">
          {githubIssues.length} issues
          {selectedIssueIds.length > 0 && ` | ${selectedIssueIds.length} selected`}
        </span>
        <div className="flex-1" />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as IssueType | 'all')}
          className="text-xs bg-friction-surface border border-friction-border rounded px-2 py-1 text-gray-300"
        >
          <option value="all">All types</option>
          <option value="bug">Bugs</option>
          <option value="feature">Features</option>
          <option value="enhancement">Enhancements</option>
          <option value="other">Other</option>
        </select>
      </div>

      {/* Issue list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {filtered.map((issue) => (
          <IssueCard
            key={issue.id}
            issue={issue}
            selected={selectedIssueIds.includes(issue.id)}
            onToggle={() => toggleIssueSelection(issue.id)}
          />
        ))}
      </div>

      {/* Generate footer */}
      {selectedIssueIds.length > 0 && (
        <div className="px-4 py-3 border-t border-friction-border bg-friction-darker/50 shrink-0">
          <button
            onClick={generateTicketsFromIssues}
            disabled={isGeneratingIssueTickets}
            className="w-full py-2.5 rounded-lg bg-friction-amber text-black font-medium text-sm hover:bg-friction-amber/90 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isGeneratingIssueTickets ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating Tickets...
              </>
            ) : (
              `Generate Tickets for Selected (${selectedIssueIds.length})`
            )}
          </button>
        </div>
      )}
    </div>
  );
}
