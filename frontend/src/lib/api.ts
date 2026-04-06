import type {
  BoardStats,
  CodebaseAnalysis,
  DeliberationSession,
  GitHubIssue,
  SessionMessage,
  Ticket,
  WorkflowGraph,
} from '@/types/friction.types';

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

function get<T>(path: string) {
  return request<T>(path);
}

function post<T>(path: string, body?: unknown) {
  return request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined });
}

function patch<T>(path: string, body: unknown) {
  return request<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
}

export const api = {
  // Sessions
  createSession: (idea: string, codebaseId?: string) =>
    post<DeliberationSession>('/sessions/', { idea, codebase_id: codebaseId }),
  listSessions: () => get<DeliberationSession[]>('/sessions/'),
  getSession: (id: string) => get<DeliberationSession>(`/sessions/${id}`),
  sendMessage: (id: string, content: string, confidenceScores?: Record<string, number>) =>
    post<SessionMessage>(`/sessions/${id}/message`, { content, confidence_scores: confidenceScores }),
  completeSession: (id: string) => post<DeliberationSession>(`/sessions/${id}/complete`),
  injectCodebase: (sessionId: string, analysisId: string) =>
    post<SessionMessage>(`/sessions/${sessionId}/inject-codebase`, { analysis_id: analysisId }),

  // Tickets
  getTickets: (sessionId: string) => get<Ticket[]>(`/sessions/${sessionId}/tickets`),
  getNextTicket: (sessionId: string, agentRole?: string) =>
    post<{ ticket: Ticket; dependency_outputs: Record<string, string> }>(
      `/sessions/${sessionId}/tickets/next`,
      { agent_role: agentRole },
    ),
  getTicket: (id: string) => get<Ticket>(`/tickets/${id}`),
  getTicketContext: (id: string) =>
    get<{ ticket: Ticket; dependency_outputs: Record<string, string> }>(`/tickets/${id}/context`),
  updateTicket: (id: string, data: Partial<Ticket>) => patch<Ticket>(`/tickets/${id}`, data),
  deleteTicket: (id: string) => request<{ deleted: boolean }>(`/tickets/${id}`, { method: 'DELETE' }),
  modifyTicket: (id: string, instruction: string) => post<Ticket>(`/tickets/${id}/modify`, { instruction }),

  // Refine
  refineTickets: (sessionId: string, content: string) =>
    post<SessionMessage>(`/sessions/${sessionId}/refine`, { content }),

  // Workflow
  getWorkflow: (sessionId: string) => get<WorkflowGraph>(`/sessions/${sessionId}/workflow`),
  getArchitecture: (sessionId: string) => get<WorkflowGraph>(`/sessions/${sessionId}/architecture`),

  // Agent Prompt
  getAgentPrompt: (sessionId: string) => get<{ prompt: string; session_id: string }>(`/sessions/${sessionId}/agent-prompt`),

  // Status
  getStatus: (sessionId: string) => get<BoardStats>(`/sessions/${sessionId}/status`),

  // Codebase
  importCodebase: (repoUrl: string, sessionId?: string) =>
    post<{ analysis: CodebaseAnalysis; issues: GitHubIssue[] }>('/codebase/import', { repo_url: repoUrl, session_id: sessionId }),
  getCodebaseAnalysis: (id: string) => get<CodebaseAnalysis>(`/codebase/${id}`),
  getCodebaseIndex: (id: string) => get<{ index: string }>(`/codebase/${id}/index`),
  getIssues: (analysisId: string) => get<GitHubIssue[]>(`/codebase/${analysisId}/issues`),
  generateIssueTickets: (analysisId: string, issueIds: string[], sessionId: string) =>
    post<Ticket[]>(`/codebase/${analysisId}/generate-tickets`, { issue_ids: issueIds, session_id: sessionId }),
  setIssueGroupActive: (sessionId: string, sourceIssueId: string, active: boolean) =>
    patch<Ticket[]>(`/sessions/${sessionId}/issue-group/${sourceIssueId}/active`, { active }),
};
