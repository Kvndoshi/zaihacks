import { useState } from 'react';
import { motion } from 'framer-motion';
import { X, Loader2, FolderGit2, Check } from 'lucide-react';
import { useFrictionStore } from '@/store/useFrictionStore';
import { api } from '@/lib/api';
import type { CodebaseAnalysis, GitHubIssue } from '@/types/friction.types';

export function ImportModal() {
  const {
    setShowImportModal,
    activeSessionId,
    setCodebaseAnalysis,
    setActiveView,
    loadSession,
  } = useFrictionStore();

  const [repoUrl, setRepoUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CodebaseAnalysis | null>(null);
  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [injecting, setInjecting] = useState(false);

  const handleImport = async () => {
    if (!repoUrl.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.importCodebase(repoUrl.trim(), activeSessionId || undefined);
      setResult(response.analysis);
      setIssues(response.issues || []);

      // Persist in store
      setCodebaseAnalysis(response.analysis);
      if (response.issues?.length) {
        useFrictionStore.setState({ githubIssues: response.issues });
      }

      // Inject codebase into the deliberation chat so Friction knows about it
      if (activeSessionId) {
        setInjecting(true);
        try {
          await api.injectCodebase(activeSessionId, response.analysis.id);
          // Reload session to get the new message + codebase_id linkage
          await loadSession(activeSessionId);
        } catch (e) {
          console.error('Failed to inject codebase into session', e);
        } finally {
          setInjecting(false);
        }
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDone = () => {
    setShowImportModal(false);
    if (issues.length > 0) {
      setActiveView('issues');
    } else {
      // Go back to deliberation so user can chat about the codebase
      setActiveView('deliberation');
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={() => setShowImportModal(false)}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="bg-friction-darker border border-friction-border rounded-xl w-[500px] max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-friction-border">
          <h2 className="text-lg font-semibold text-gray-200 flex items-center gap-2">
            <FolderGit2 className="w-5 h-5 text-friction-amber" />
            Import Codebase
          </h2>
          <button onClick={() => setShowImportModal(false)} className="text-gray-400 hover:text-gray-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {!result ? (
            <>
              <div>
                <label className="text-sm text-gray-400 block mb-1">Git Repository URL</label>
                <input
                  type="text"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/user/repo.git"
                  className="w-full bg-friction-surface border border-friction-border rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-500 focus:outline-none focus:border-friction-amber/50"
                  onKeyDown={(e) => e.key === 'Enter' && handleImport()}
                />
              </div>

              {error && <p className="text-sm text-friction-red">{error}</p>}

              <button
                onClick={handleImport}
                disabled={!repoUrl.trim() || loading}
                className="w-full py-2.5 rounded-lg bg-friction-amber text-black font-medium text-sm hover:bg-friction-amber/90 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {injecting ? 'Injecting into deliberation...' : 'Cloning & Analyzing...'}
                  </>
                ) : (
                  'Import & Analyze'
                )}
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 text-green-400">
                <Check className="w-5 h-5" />
                <span className="font-medium">Codebase imported into deliberation</span>
              </div>

              <div className="bg-friction-surface rounded-lg p-4 text-sm space-y-2">
                <p className="text-gray-300">{result.summary}</p>
                <div className="grid grid-cols-2 gap-2 text-xs text-friction-muted mt-3">
                  <div>Files: {result.file_count}</div>
                  <div>Size: {(result.total_size / 1024).toFixed(0)} KB</div>
                  <div>Languages: {Object.keys(result.tech_stack.languages).join(', ')}</div>
                  <div>Frameworks: {result.tech_stack.frameworks.join(', ') || 'None detected'}</div>
                </div>
                {issues.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-friction-border text-xs text-friction-amber">
                    {issues.length} open GitHub issues found
                  </div>
                )}
              </div>

              <button
                onClick={handleDone}
                className="w-full py-2 rounded-lg bg-friction-amber text-black font-medium text-sm hover:bg-friction-amber/90"
              >
                {issues.length > 0
                  ? `View ${issues.length} GitHub Issues`
                  : 'Chat About This Codebase'}
              </button>
            </>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
