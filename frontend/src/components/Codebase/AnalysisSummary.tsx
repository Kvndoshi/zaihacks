import type { CodebaseAnalysis } from '@/types/friction.types';

interface AnalysisSummaryProps {
  analysis: CodebaseAnalysis;
}

export function AnalysisSummary({ analysis }: AnalysisSummaryProps) {
  return (
    <div className="bg-friction-surface rounded-lg p-4 border border-friction-border">
      <h3 className="text-sm font-semibold text-gray-300 mb-2">Codebase Analysis</h3>
      <p className="text-xs text-gray-400 mb-3">{analysis.summary}</p>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <span className="text-friction-muted">Languages</span>
          <div className="mt-1 space-y-0.5">
            {Object.entries(analysis.tech_stack.languages).map(([lang, count]) => (
              <div key={lang} className="text-gray-300">
                {lang}: {count} files
              </div>
            ))}
          </div>
        </div>
        <div>
          <span className="text-friction-muted">Frameworks</span>
          <div className="mt-1 space-y-0.5">
            {analysis.tech_stack.frameworks.map((fw) => (
              <div key={fw} className="text-gray-300">{fw}</div>
            ))}
          </div>
        </div>
      </div>

      {analysis.architecture_patterns.length > 0 && (
        <div className="mt-3">
          <span className="text-xs text-friction-muted">Patterns</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {analysis.architecture_patterns.map((p) => (
              <span
                key={p.name}
                className="text-[10px] px-1.5 py-0.5 rounded-full bg-friction-amber/10 text-friction-amber"
              >
                {p.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
