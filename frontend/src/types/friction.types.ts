// ---- Session ----

export type SessionStatus = 'deliberating' | 'generating_tickets' | 'completed' | 'archived';
export type MessageRole = 'user' | 'friction' | 'system';

export interface SessionMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  confidence_score?: number | null;
  phase?: string | null;
  web_searched?: boolean;
}

export interface DeliberationSession {
  id: string;
  title: string;
  idea: string;
  status: SessionStatus;
  messages: SessionMessage[];
  key_insights: string[];
  risks: string[];
  refined_idea?: string | null;
  codebase_id?: string | null;
  agent_prompt?: string | null;
  created_at: string;
  updated_at: string;
}

// ---- Tickets ----

export type TicketStatus = 'blocked' | 'ready' | 'in_progress' | 'completed' | 'failed';
export type TicketPriority = 0 | 1 | 2 | 3;
export type TicketDomain = 'backend' | 'frontend' | 'database' | 'auth' | 'api' | 'testing' | 'infra' | 'docs' | 'marketing' | 'design' | 'research' | 'operations' | 'content' | 'legal' | 'business' | 'general';

export interface Ticket {
  id: string;
  session_id: string;
  title: string;
  description: string;
  layer: number;
  domain: TicketDomain;
  priority: TicketPriority;
  status: TicketStatus;
  depends_on: string[];
  blocks: string[];
  acceptance_criteria: string[];
  files_to_create: string[];
  files_to_modify: string[];
  output_summary?: string | null;
  agent_id?: string | null;
  source_issue_id?: string | null;
  source_issue_title?: string | null;
  active?: boolean;
  claimed_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

// ---- Workflow ----

export interface WorkflowNode {
  id: string;
  ticket_id: string;
  label: string;
  layer: number;
  domain: TicketDomain;
  status: TicketStatus;
  position_x: number;
  position_y: number;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  animated: boolean;
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

// ---- Codebase ----

export interface FileInfo {
  path: string;
  size: number;
  language: string;
  is_config: boolean;
}

export interface TechStackInfo {
  languages: Record<string, number>;
  frameworks: string[];
  package_managers: string[];
  databases: string[];
}

export interface ArchitecturePattern {
  name: string;
  description: string;
  confidence: number;
}

export interface CodebaseAnalysis {
  id: string;
  session_id?: string | null;
  repo_url?: string | null;
  tech_stack: TechStackInfo;
  architecture_patterns: ArchitecturePattern[];
  key_files: FileInfo[];
  summary: string;
  file_count: number;
  total_size: number;
  codebase_index?: string | null;
}

// ---- GitHub Issues ----

export type IssueType = 'bug' | 'feature' | 'enhancement' | 'other';

export interface GitHubLabel {
  name: string;
  color: string;
}

export interface GitHubIssue {
  id: string;
  github_id: number;
  title: string;
  body: string;
  state: string;
  labels: GitHubLabel[];
  issue_type: IssueType;
  html_url: string;
  created_at: string;
}

// ---- Events ----

export type EventType =
  | 'session_created'
  | 'session_message'
  | 'deliberation_complete'
  | 'tickets_generated'
  | 'tickets_refined'
  | 'ticket_claimed'
  | 'ticket_completed'
  | 'ticket_failed'
  | 'ticket_deleted'
  | 'ticket_modified'
  | 'workflow_update'
  | 'agent_connected'
  | 'agent_disconnected'
  | 'status_update'
  | 'issues_fetched'
  | 'issue_tickets_generated'
  | 'issue_group_toggled';

export interface WSEvent {
  type: EventType;
  data: Record<string, unknown>;
  session_id: string;
  timestamp: string;
}

// ---- Board Stats ----

export interface BoardStats {
  total: number;
  completed: number;
  in_progress: number;
  blocked: number;
  ready: number;
  failed?: number;
  percent_complete: number;
  layers: Record<number, { total: number; completed: number }>;
}
