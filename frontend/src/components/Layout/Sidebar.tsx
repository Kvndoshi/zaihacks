import { useState } from 'react';
import { Plus, FolderGit2, MessageSquare, CheckCircle2, Archive, ChevronLeft, ChevronRight } from 'lucide-react';
import { useFrictionStore } from '@/store/useFrictionStore';
import { cn } from '@/lib/utils';

export function Sidebar() {
  const {
    sessions,
    activeSessionId,
    loadSession,
    createSession,
    setShowImportModal,
    sidebarCollapsed,
    toggleSidebar,
  } = useFrictionStore();

  const [newIdea, setNewIdea] = useState('');
  const [showInput, setShowInput] = useState(false);

  const handleCreate = async () => {
    if (!newIdea.trim()) return;
    await createSession(newIdea.trim());
    setNewIdea('');
    setShowInput(false);
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case 'deliberating': return <MessageSquare className="w-3.5 h-3.5 text-friction-amber" />;
      case 'completed': return <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />;
      case 'archived': return <Archive className="w-3.5 h-3.5 text-gray-500" />;
      default: return <MessageSquare className="w-3.5 h-3.5 text-gray-500" />;
    }
  };

  return (
    <>
    {sidebarCollapsed && (
      <button
        onClick={toggleSidebar}
        className="fixed left-0 top-14 z-40 w-7 h-7 flex items-center justify-center rounded-r-full bg-friction-amber text-black hover:bg-friction-amber/90 transition-colors shadow-lg"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    )}
    <aside className={cn(
      'border-r border-friction-border bg-friction-darker flex flex-col shrink-0 transition-all duration-300',
      sidebarCollapsed ? 'w-0 overflow-hidden' : 'w-60',
    )}>
      <div className="p-3 space-y-2">
        <div className="flex items-center justify-between">
          <button
            onClick={() => setShowInput(true)}
            className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg bg-friction-amber/10 text-friction-amber hover:bg-friction-amber/20 transition-colors text-sm font-medium"
          >
            <Plus className="w-4 h-4" />
            New Deliberation
          </button>
          <button
            onClick={toggleSidebar}
            className="ml-2 w-7 h-7 flex items-center justify-center rounded-full bg-friction-amber/20 text-friction-amber hover:bg-friction-amber/30 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>
        <button
          onClick={() => setShowImportModal(true)}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-gray-400 hover:bg-friction-surface hover:text-gray-200 transition-colors text-sm"
        >
          <FolderGit2 className="w-4 h-4" />
          Import Codebase
        </button>
      </div>

      {showInput && (
        <div className="px-3 pb-3">
          <textarea
            value={newIdea}
            onChange={(e) => setNewIdea(e.target.value)}
            placeholder="Describe your idea..."
            className="w-full bg-friction-surface border border-friction-border rounded-lg px-3 py-2 text-sm text-gray-200 placeholder:text-gray-500 resize-none focus:outline-none focus:border-friction-amber/50"
            rows={3}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleCreate();
              }
              if (e.key === 'Escape') setShowInput(false);
            }}
          />
          <div className="flex gap-2 mt-2">
            <button
              onClick={handleCreate}
              className="flex-1 py-1.5 text-xs font-medium rounded-md bg-friction-amber text-black hover:bg-friction-amber/90"
            >
              Start
            </button>
            <button
              onClick={() => setShowInput(false)}
              className="px-3 py-1.5 text-xs rounded-md text-gray-400 hover:text-gray-200 hover:bg-friction-surface"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {sessions.map((session) => (
          <button
            key={session.id}
            onClick={() => loadSession(session.id)}
            className={cn(
              'w-full text-left px-3 py-2.5 border-b border-friction-border/50 hover:bg-friction-surface transition-colors',
              activeSessionId === session.id && 'bg-friction-surface border-l-2 border-l-friction-amber',
            )}
          >
            <div className="flex items-start gap-2">
              {statusIcon(session.status)}
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{session.title}</p>
                <p className="text-xs text-friction-muted mt-0.5">
                  {session.messages.length} messages
                </p>
              </div>
            </div>
          </button>
        ))}
      </div>
    </aside>
    </>
  );
}
