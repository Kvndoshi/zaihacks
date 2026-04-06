import { useEffect, useState } from 'react';
import { useWebSocket } from '@/store/useWebSocket';
import { useFrictionStore } from '@/store/useFrictionStore';
import { Header } from '@/components/Layout/Header';
import { Sidebar } from '@/components/Layout/Sidebar';
import { DeliberationChat } from '@/components/Deliberation/DeliberationChat';
import { DeliberationSummary } from '@/components/Deliberation/DeliberationSummary';
import { WorkflowGraph } from '@/components/Workflow/WorkflowGraph';
import { TicketBoard } from '@/components/Tickets/TicketBoard';
import { TicketDetail } from '@/components/Tickets/TicketDetail';
import { StatusBar } from '@/components/Dashboard/StatusBar';
import { EventFeed } from '@/components/Dashboard/EventFeed';
import { ImportModal } from '@/components/Codebase/ImportModal';
import { CodebaseSummary } from '@/components/Codebase/CodebaseSummary';
import { IssuesPanel } from '@/components/Issues/IssuesPanel';
import { Flame, MessageSquare, X } from 'lucide-react';

export default function App() {
  const { connected } = useWebSocket();
  const {
    activeSessionId,
    activeSession,
    activeView,
    tickets,
    selectedTicketId,
    showImportModal,
    loadSessions,
    codebaseAnalysis,
  } = useFrictionStore();

  const [chatPanelOpen, setChatPanelOpen] = useState(true);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const hasTickets = tickets.length > 0;
  const isCompleted = activeSession?.status === 'completed';

  // Determine chat panel width
  const getChatPanelClass = () => {
    // During deliberation, chat always stays visible
    if (!hasTickets && activeView === 'deliberation') return 'w-2/3 min-w-[400px]';
    if (!hasTickets && activeView === 'issues') return 'w-[35%] min-w-[300px]';
    if (!hasTickets) return 'w-1/2 min-w-[400px]';
    if (hasTickets && isCompleted && chatPanelOpen) return 'w-[35%] min-w-[320px]';
    if (hasTickets && activeView === 'deliberation') return 'w-1/2 min-w-[400px]';
    if (hasTickets && !chatPanelOpen) return 'w-0 overflow-hidden';
    return 'w-0 overflow-hidden';
  };

  return (
    <div className="h-screen flex flex-col bg-friction-dark text-gray-200 overflow-hidden">
      <Header connected={connected} />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        <main className="flex-1 flex overflow-hidden">
          {!activeSessionId ? (
            <WelcomeScreen />
          ) : (
            <>
              {/* Left panel: Deliberation Chat */}
              <div className={`flex flex-col border-r border-friction-border transition-all duration-300 ${getChatPanelClass()}`}>
                <DeliberationChat />
                {isCompleted && !hasTickets && <DeliberationSummary />}
              </div>

              {/* Right panel: Workflow / Tickets */}
              <div className={`flex flex-col flex-1 overflow-hidden transition-all duration-300 relative ${
                !hasTickets && !isCompleted && activeView !== 'issues' ? 'items-center justify-center' : ''
              }`}>
                {/* Chat toggle button when panel is hidden */}
                {hasTickets && isCompleted && !chatPanelOpen && (
                  <button
                    onClick={() => setChatPanelOpen(true)}
                    className="absolute top-2 left-2 z-10 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-friction-amber/10 text-friction-amber hover:bg-friction-amber/20 transition-colors text-xs font-medium"
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    Chat
                  </button>
                )}
                {hasTickets && isCompleted && chatPanelOpen && (
                  <button
                    onClick={() => setChatPanelOpen(false)}
                    className="absolute top-2 left-2 z-10 flex items-center gap-1 px-2 py-1 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-friction-surface transition-colors text-xs"
                    title="Hide chat panel"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}

                {activeView === 'issues' ? (
                  <IssuesPanel />
                ) : activeView === 'workflow' && hasTickets ? (
                  <WorkflowGraph />
                ) : hasTickets ? (
                  <TicketBoard />
                ) : !isCompleted && codebaseAnalysis && activeView === 'deliberation' ? (
                  <CodebaseSummary />
                ) : !hasTickets && !isCompleted ? (
                  <div className="text-center text-friction-muted p-8">
                    <Flame className="w-12 h-12 mx-auto mb-4 text-friction-amber opacity-30" />
                    <p className="text-lg">Deliberation in progress...</p>
                    <p className="text-sm mt-2">The workflow will appear here as tickets are generated.</p>
                  </div>
                ) : (
                  <TicketBoard />
                )}
              </div>
            </>
          )}
        </main>
      </div>

      {hasTickets && <StatusBar />}
      <EventFeed />

      {selectedTicketId && <TicketDetail />}
      {showImportModal && <ImportModal />}
    </div>
  );
}

function WelcomeScreen() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center max-w-lg">
        <Flame className="w-20 h-20 mx-auto mb-6 text-friction-amber" />
        <h1 className="text-4xl font-bold mb-3 amber-glow">FRICTION</h1>
        <p className="text-xl text-gray-400 mb-2">The AI that debates your idea first.</p>
        <p className="text-sm text-friction-muted mt-6">
          Create a new deliberation from the sidebar to get started.
        </p>
      </div>
    </div>
  );
}
