import { cn } from '@/lib/utils';
import type { GitHubIssue, IssueType } from '@/types/friction.types';
import { ExternalLink } from 'lucide-react';

const TYPE_BADGE: Record<IssueType, string> = {
  bug: 'bg-red-500/20 text-red-400',
  feature: 'bg-green-500/20 text-green-400',
  enhancement: 'bg-blue-500/20 text-blue-400',
  other: 'bg-gray-500/20 text-gray-400',
};

interface IssueCardProps {
  issue: GitHubIssue;
  selected: boolean;
  onToggle: () => void;
}

export function IssueCard({ issue, selected, onToggle }: IssueCardProps) {
  return (
    <div
      className={cn(
        'bg-friction-surface rounded-lg border border-friction-border p-3 cursor-pointer transition-all hover:border-friction-border/80',
        selected && 'border-friction-amber/50 bg-friction-amber/5',
      )}
      onClick={onToggle}
    >
      <div className="flex items-start gap-2">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          onClick={(e) => e.stopPropagation()}
          className="mt-1 shrink-0 accent-[#f59e0b]"
        />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={cn('text-[9px] px-1.5 py-0.5 rounded-full font-medium', TYPE_BADGE[issue.issue_type])}>
              {issue.issue_type}
            </span>
            <span className="text-[10px] text-friction-muted">#{issue.github_id}</span>
            {issue.html_url && (
              <a
                href={issue.html_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-friction-muted hover:text-friction-amber transition-colors ml-auto"
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>

          <h4 className="text-xs font-medium text-gray-200 leading-snug line-clamp-2">
            {issue.title}
          </h4>

          {issue.body && (
            <p className="text-[10px] text-friction-muted mt-1 line-clamp-2">
              {issue.body}
            </p>
          )}

          {issue.labels.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {issue.labels.map((lbl) => (
                <span
                  key={lbl.name}
                  className="text-[9px] px-1.5 py-0.5 rounded-full"
                  style={{
                    backgroundColor: lbl.color ? `#${lbl.color}22` : '#6b728022',
                    color: lbl.color ? `#${lbl.color}` : '#9ca3af',
                  }}
                >
                  {lbl.name}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
