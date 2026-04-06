import { useState } from 'react';
import { useFrictionStore } from '@/store/useFrictionStore';
import { FolderGit2, FileCode, Box, Database, Map, Copy, Check, ChevronDown, ChevronRight } from 'lucide-react';

export function CodebaseSummary() {
  const { codebaseAnalysis, githubIssues, setActiveView } = useFrictionStore();
  const [showIndex, setShowIndex] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!codebaseAnalysis) return null;

  const { tech_stack, summary, file_count, total_size, repo_url, codebase_index } = codebaseAnalysis;
  const repoName = repo_url
    ? repo_url.replace(/\.git$/, '').split('/').slice(-2).join('/')
    : 'Imported Codebase';

  const handleCopyIndex = async () => {
    if (!codebase_index) return;
    try {
      await navigator.clipboard.writeText(codebase_index);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = codebase_index;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-8 text-center overflow-y-auto">
      <FolderGit2 className="w-12 h-12 text-friction-amber mb-4" />
      <h2 className="text-lg font-semibold text-gray-200 mb-1">{repoName}</h2>
      <p className="text-sm text-gray-400 max-w-md mb-6">{summary}</p>

      <div className="grid grid-cols-2 gap-3 w-full max-w-sm mb-6">
        <div className="bg-friction-surface rounded-lg border border-friction-border p-3 flex items-center gap-2">
          <FileCode className="w-4 h-4 text-friction-amber shrink-0" />
          <div className="text-left">
            <div className="text-sm font-medium text-gray-200">{file_count}</div>
            <div className="text-[10px] text-friction-muted">Files</div>
          </div>
        </div>
        <div className="bg-friction-surface rounded-lg border border-friction-border p-3 flex items-center gap-2">
          <Box className="w-4 h-4 text-friction-amber shrink-0" />
          <div className="text-left">
            <div className="text-sm font-medium text-gray-200">{(total_size / 1024).toFixed(0)} KB</div>
            <div className="text-[10px] text-friction-muted">Total size</div>
          </div>
        </div>
      </div>

      {Object.keys(tech_stack.languages).length > 0 && (
        <div className="flex flex-wrap gap-1.5 justify-center mb-3">
          {Object.entries(tech_stack.languages).map(([lang, count]) => (
            <span
              key={lang}
              className="text-[10px] px-2 py-0.5 rounded-full bg-friction-surface border border-friction-border text-gray-300"
            >
              {lang} ({count})
            </span>
          ))}
        </div>
      )}

      {tech_stack.frameworks.length > 0 && (
        <div className="flex flex-wrap gap-1.5 justify-center mb-3">
          {tech_stack.frameworks.map((fw) => (
            <span
              key={fw}
              className="text-[10px] px-2 py-0.5 rounded-full bg-friction-amber/10 text-friction-amber border border-friction-amber/20"
            >
              {fw}
            </span>
          ))}
        </div>
      )}

      {tech_stack.databases.length > 0 && (
        <div className="flex flex-wrap gap-1.5 justify-center mb-4">
          {tech_stack.databases.map((db) => (
            <span
              key={db}
              className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1"
            >
              <Database className="w-2.5 h-2.5" />
              {db}
            </span>
          ))}
        </div>
      )}

      {codebase_index && (
        <div className="w-full max-w-2xl mb-4">
          <button
            onClick={() => setShowIndex(!showIndex)}
            className="flex items-center gap-2 w-full px-4 py-2.5 rounded-lg bg-friction-surface border border-friction-border text-gray-200 hover:border-friction-amber/40 transition-colors text-sm font-medium"
          >
            <Map className="w-4 h-4 text-friction-amber shrink-0" />
            <span>Codebase Map</span>
            {showIndex ? (
              <ChevronDown className="w-4 h-4 text-friction-muted ml-auto" />
            ) : (
              <ChevronRight className="w-4 h-4 text-friction-muted ml-auto" />
            )}
          </button>
          {showIndex && (
            <div className="mt-2 relative">
              <button
                onClick={handleCopyIndex}
                className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 rounded bg-friction-surface border border-friction-border text-xs text-gray-400 hover:text-gray-200 hover:border-friction-amber/40 transition-colors z-10"
                title="Copy index to clipboard"
              >
                {copied ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copy Index</span>
                  </>
                )}
              </button>
              <pre className="text-left text-[11px] leading-relaxed text-gray-300 bg-[#0a0a0a] border border-friction-border rounded-lg p-4 pr-24 overflow-x-auto max-h-[400px] overflow-y-auto font-mono whitespace-pre">
                {codebase_index}
              </pre>
            </div>
          )}
        </div>
      )}

      {githubIssues.length > 0 && (
        <button
          onClick={() => setActiveView('issues')}
          className="mt-2 px-4 py-2 rounded-lg bg-friction-amber text-black font-medium text-sm hover:bg-friction-amber/90"
        >
          View {githubIssues.length} GitHub Issues
        </button>
      )}

      <p className="text-xs text-friction-muted mt-6 max-w-xs">
        Codebase imported. Continue the deliberation to discuss what you want to build or change.
      </p>
    </div>
  );
}
