import { create } from 'zustand';
import { api } from '@/lib/api';
import type {
  BoardStats,
  CodebaseAnalysis,
  DeliberationSession,
  GitHubIssue,
  SessionMessage,
  Ticket,
  WorkflowGraph,
  WSEvent,
} from '@/types/friction.types';

export type ActiveView = 'deliberation' | 'tickets' | 'workflow' | 'issues';

interface FrictionState {
  sessions: DeliberationSession[];
  activeSessionId: string | null;
  activeSession: DeliberationSession | null;
  messages: SessionMessage[];
  isDeliberating: boolean;
  isGeneratingTickets: boolean;
  tickets: Ticket[];
  selectedTicketId: string | null;
  workflow: WorkflowGraph | null;
  architectureGraph: WorkflowGraph | null;
  workflowMode: 'detailed' | 'highlevel';
  codebaseAnalysis: CodebaseAnalysis | null;
  activeView: ActiveView;
  showImportModal: boolean;
  events: WSEvent[];
  boardStats: BoardStats | null;
  isSending: boolean;
  sidebarCollapsed: boolean;
  showAgentPrompt: boolean;

  // GitHub Issues state
  githubIssues: GitHubIssue[];
  selectedIssueIds: string[];
  isGeneratingIssueTickets: boolean;

  // Actions
  createSession: (idea: string) => Promise<void>;
  sendMessage: (content: string, confidenceScores?: Record<string, number>) => Promise<void>;
  completeDeliberation: () => Promise<void>;
  loadSession: (id: string) => Promise<void>;
  loadSessions: () => Promise<void>;
  loadTickets: () => Promise<void>;
  loadWorkflow: () => Promise<void>;
  loadStatus: () => Promise<void>;
  addEvent: (event: WSEvent) => void;
  setActiveView: (view: ActiveView) => void;
  selectTicket: (id: string | null) => void;
  setShowImportModal: (show: boolean) => void;
  toggleSidebar: () => void;
  deleteTicket: (id: string) => Promise<void>;
  modifyTicket: (id: string, instruction: string) => Promise<void>;
  refineTickets: (content: string) => Promise<void>;
  toggleWorkflowMode: () => void;
  loadArchitecture: () => Promise<void>;
  handleWSEvent: (event: WSEvent) => void;

  // Codebase + Issues actions
  setCodebaseAnalysis: (analysis: CodebaseAnalysis | null) => void;
  loadCodebaseAnalysis: () => Promise<void>;
  loadIssues: () => Promise<void>;
  toggleIssueSelection: (id: string) => void;
  selectAllIssues: () => void;
  deselectAllIssues: () => void;
  generateTicketsFromIssues: () => Promise<void>;
  toggleTicketComplete: (id: string) => Promise<void>;
  toggleIssueGroupActive: (sourceIssueId: string) => Promise<void>;
  setShowAgentPrompt: (show: boolean) => void;
}

export const useFrictionStore = create<FrictionState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  activeSession: null,
  messages: [],
  isDeliberating: false,
  isGeneratingTickets: false,
  tickets: [],
  selectedTicketId: null,
  workflow: null,
  architectureGraph: null,
  workflowMode: 'detailed' as const,
  codebaseAnalysis: null,
  activeView: 'deliberation',
  showImportModal: false,
  events: [],
  boardStats: null,
  isSending: false,
  sidebarCollapsed: false,
  showAgentPrompt: false,

  // GitHub Issues state
  githubIssues: [],
  selectedIssueIds: [],
  isGeneratingIssueTickets: false,

  createSession: async (idea: string) => {
    set({ isDeliberating: true });
    try {
      const session = await api.createSession(idea);
      set({
        activeSessionId: session.id,
        activeSession: session,
        messages: session.messages,
        isDeliberating: false,
        activeView: 'deliberation',
        tickets: [],
        workflow: null,
      });
      get().loadSessions();
    } catch (e) {
      set({ isDeliberating: false });
      throw e;
    }
  },

  sendMessage: async (content: string, confidenceScores?: Record<string, number>) => {
    const { activeSessionId, messages } = get();
    if (!activeSessionId) return;

    // Optimistically add user message
    const userMsg: SessionMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
      confidence_score: confidenceScores
        ? Object.values(confidenceScores).reduce((a, b) => a + b, 0) / Object.values(confidenceScores).length
        : null,
    };
    set({ messages: [...messages, userMsg], isSending: true });

    try {
      const aiMsg = await api.sendMessage(activeSessionId, content, confidenceScores);
      set((s) => ({ messages: [...s.messages, aiMsg], isSending: false }));
    } catch (e) {
      set({ isSending: false });
      throw e;
    }
  },

  completeDeliberation: async () => {
    const { activeSessionId } = get();
    if (!activeSessionId) return;

    set({ isGeneratingTickets: true });
    try {
      const session = await api.completeSession(activeSessionId);
      set({
        activeSession: session,
        messages: session.messages,
        isGeneratingTickets: false,
      });
      await get().loadTickets();
      await get().loadWorkflow();
      set({ activeView: 'tickets', showAgentPrompt: true });
    } catch (e) {
      set({ isGeneratingTickets: false });
      throw e;
    }
  },

  loadSession: async (id: string) => {
    const session = await api.getSession(id);
    set({
      activeSessionId: id,
      activeSession: session,
      messages: session.messages,
    });
    if (session.status === 'completed') {
      get().loadTickets();
      get().loadWorkflow();
      get().loadStatus();
    }
    // Load codebase analysis if linked
    if (session.codebase_id) {
      get().loadCodebaseAnalysis();
    }
  },

  loadSessions: async () => {
    const sessions = await api.listSessions();
    set({ sessions });
  },

  loadTickets: async () => {
    const { activeSessionId } = get();
    if (!activeSessionId) return;
    try {
      const tickets = await api.getTickets(activeSessionId);
      set({ tickets });
    } catch {
      /* no tickets yet */
    }
  },

  loadWorkflow: async () => {
    const { activeSessionId } = get();
    if (!activeSessionId) return;
    try {
      const workflow = await api.getWorkflow(activeSessionId);
      set({ workflow });
    } catch {
      /* no workflow yet */
    }
  },

  loadStatus: async () => {
    const { activeSessionId } = get();
    if (!activeSessionId) return;
    try {
      const stats = await api.getStatus(activeSessionId);
      set({ boardStats: stats });
    } catch {
      /* ignore */
    }
  },

  addEvent: (event: WSEvent) => {
    set((s) => ({ events: [...s.events.slice(-99), event] }));
  },

  setActiveView: (view: ActiveView) => set({ activeView: view }),

  selectTicket: (id: string | null) => set({ selectedTicketId: id }),

  setShowImportModal: (show: boolean) => set({ showImportModal: show }),

  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  deleteTicket: async (id: string) => {
    const { selectedTicketId } = get();
    try {
      await api.deleteTicket(id);
      set((s) => ({
        tickets: s.tickets.filter((t) => t.id !== id),
        selectedTicketId: selectedTicketId === id ? null : selectedTicketId,
      }));
      get().loadWorkflow();
    } catch (e) {
      console.error('Failed to delete ticket', e);
    }
  },

  modifyTicket: async (id: string, instruction: string) => {
    try {
      const updated = await api.modifyTicket(id, instruction);
      set((s) => ({
        tickets: s.tickets.map((t) => (t.id === updated.id ? updated : t)),
      }));
      get().loadWorkflow();
    } catch (e) {
      console.error('Failed to modify ticket', e);
    }
  },

  toggleWorkflowMode: () => {
    const { workflowMode, architectureGraph } = get();
    if (workflowMode === 'detailed') {
      set({ workflowMode: 'highlevel' });
      if (!architectureGraph) {
        get().loadArchitecture();
      }
    } else {
      set({ workflowMode: 'detailed' });
    }
  },

  loadArchitecture: async () => {
    const { activeSessionId } = get();
    if (!activeSessionId) return;
    try {
      const graph = await api.getArchitecture(activeSessionId);
      set({ architectureGraph: graph });
    } catch (e) {
      console.error('Failed to load architecture', e);
    }
  },

  refineTickets: async (content: string) => {
    const { activeSessionId, messages } = get();
    if (!activeSessionId) return;

    // Optimistically add user message
    const userMsg: SessionMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    set({ messages: [...messages, userMsg], isSending: true });

    try {
      const aiMsg = await api.refineTickets(activeSessionId, content);
      set((s) => ({ messages: [...s.messages, aiMsg], isSending: false }));
      get().loadTickets();
      get().loadWorkflow();
      get().loadStatus();
    } catch (e) {
      set({ isSending: false });
      console.error('Failed to refine tickets', e);
    }
  },

  handleWSEvent: (event: WSEvent) => {
    get().addEvent(event);
    const { activeSessionId } = get();
    if (event.session_id !== activeSessionId) return;

    switch (event.type) {
      case 'session_message': {
        // Real-time message from inject-codebase or other server-side actions.
        // Skip if we're in an active send/refine flow — the API response handler
        // already appends the message, so the WS event would duplicate it.
        if (get().isSending) break;

        const data = event.data as { message_id?: string; role?: string; content?: string; web_searched?: boolean };
        if (data?.content && data?.role && data?.message_id) {
          const existing = get().messages.find((m) => m.id === data.message_id);
          if (!existing) {
            set((s) => ({
              messages: [...s.messages, {
                id: data.message_id!,
                role: data.role as 'user' | 'friction',
                content: data.content!,
                timestamp: new Date().toISOString(),
                web_searched: data.web_searched ?? false,
              }],
            }));
          }
        }
        break;
      }
      case 'tickets_generated':
      case 'issue_tickets_generated':
        get().loadTickets();
        get().loadWorkflow();
        get().loadStatus();
        break;
      case 'ticket_claimed':
      case 'ticket_completed':
      case 'ticket_failed':
      case 'workflow_update':
      case 'ticket_deleted':
      case 'ticket_modified':
      case 'tickets_refined':
      case 'issue_group_toggled':
        get().loadTickets();
        get().loadWorkflow();
        get().loadStatus();
        break;
    }
  },

  // ------------------------------------------------------------------
  // Codebase + Issues actions
  // ------------------------------------------------------------------

  setCodebaseAnalysis: (analysis: CodebaseAnalysis | null) => {
    set({ codebaseAnalysis: analysis });
  },

  loadCodebaseAnalysis: async () => {
    const { activeSession } = get();
    if (!activeSession?.codebase_id) return;
    try {
      const analysis = await api.getCodebaseAnalysis(activeSession.codebase_id);
      set({ codebaseAnalysis: analysis });
      // Also load issues
      get().loadIssues();
    } catch (e) {
      console.error('Failed to load codebase analysis', e);
    }
  },

  loadIssues: async () => {
    const { codebaseAnalysis } = get();
    if (!codebaseAnalysis) return;
    try {
      const issues = await api.getIssues(codebaseAnalysis.id);
      set({ githubIssues: issues });
    } catch (e) {
      console.error('Failed to load issues', e);
    }
  },

  toggleIssueSelection: (id: string) => {
    set((s) => {
      const selected = s.selectedIssueIds.includes(id)
        ? s.selectedIssueIds.filter((i) => i !== id)
        : [...s.selectedIssueIds, id];
      return { selectedIssueIds: selected };
    });
  },

  selectAllIssues: () => {
    set((s) => ({ selectedIssueIds: s.githubIssues.map((i) => i.id) }));
  },

  deselectAllIssues: () => {
    set({ selectedIssueIds: [] });
  },

  generateTicketsFromIssues: async () => {
    const { codebaseAnalysis, selectedIssueIds, activeSessionId } = get();
    if (!codebaseAnalysis || !activeSessionId || selectedIssueIds.length === 0) return;

    set({ isGeneratingIssueTickets: true });
    try {
      await api.generateIssueTickets(codebaseAnalysis.id, selectedIssueIds, activeSessionId);
      await get().loadTickets();
      await get().loadWorkflow();
      await get().loadStatus();
      set({ activeView: 'tickets', isGeneratingIssueTickets: false, selectedIssueIds: [], showAgentPrompt: true });
    } catch (e) {
      set({ isGeneratingIssueTickets: false });
      console.error('Failed to generate tickets from issues', e);
    }
  },

  setShowAgentPrompt: (show: boolean) => set({ showAgentPrompt: show }),

  toggleTicketComplete: async (id: string) => {
    const { tickets } = get();
    const ticket = tickets.find((t) => t.id === id);
    if (!ticket) return;

    const newStatus = ticket.status === 'completed' ? 'ready' : 'completed';

    // Optimistically update
    set((s) => ({
      tickets: s.tickets.map((t) =>
        t.id === id ? { ...t, status: newStatus } : t
      ),
    }));

    try {
      await api.updateTicket(id, { status: newStatus } as Partial<Ticket>);
      // Reload to get server-side dependency unlocking changes
      get().loadTickets();
      get().loadWorkflow();
      get().loadStatus();
    } catch (e) {
      // Revert on failure
      set((s) => ({
        tickets: s.tickets.map((t) =>
          t.id === id ? { ...t, status: ticket.status } : t
        ),
      }));
      console.error('Failed to toggle ticket completion', e);
    }
  },

  toggleIssueGroupActive: async (sourceIssueId: string) => {
    const { activeSessionId, tickets } = get();
    if (!activeSessionId) return;

    // Determine current state from first matching ticket
    const groupTicket = tickets.find((t) => t.source_issue_id === sourceIssueId);
    const currentActive = groupTicket?.active !== false;
    const newActive = !currentActive;

    try {
      await api.setIssueGroupActive(activeSessionId, sourceIssueId, newActive);
      // Optimistically update
      set((s) => ({
        tickets: s.tickets.map((t) =>
          t.source_issue_id === sourceIssueId ? { ...t, active: newActive } : t
        ),
      }));
      get().loadWorkflow();
    } catch (e) {
      console.error('Failed to toggle issue group', e);
    }
  },
}));
