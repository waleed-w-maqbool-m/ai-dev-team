// Mirrors the backend's Pydantic schemas (schemas/*.py). Payloads are typed
// loosely on purpose: replays recorded by older versions of the pipeline may
// be missing newer fields, and the UI has to degrade gracefully.

export type AgentId = "pm" | "swe" | "testing" | "qa" | "docs";

export const AGENTS: AgentId[] = ["pm", "swe", "testing", "qa", "docs"];

export const AGENT_META: Record<AgentId, { name: string; short: string; sender: string }> = {
  pm: { name: "Project Manager", short: "PM", sender: "project_manager" },
  swe: { name: "Software Engineer", short: "SWE", sender: "software_engineer" },
  testing: { name: "Testing Agent", short: "TEST", sender: "testing_agent" },
  qa: { name: "QA Reviewer", short: "QA", sender: "qa_reviewer" },
  docs: { name: "Documentation", short: "DOCS", sender: "documentation" },
};

export type MessageType =
  | "plan"
  | "implementation"
  | "test_report"
  | "review"
  | "clarification_request"
  | "documentation"
  | "status";

export interface AgentMessage {
  sender: string;
  message_type: MessageType;
  payload: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  timestamp?: string;
}

export type TaskStatus = "pending" | "in_progress" | "in_review" | "done" | "blocked_needs_human";

export interface Criterion {
  id: string;
  description: string;
}

export interface FileChange {
  path: string;
  action: "create" | "modify" | "delete";
  content: string;
}

export interface TestCheck {
  file: string;
  check: string;
  passed: boolean;
  detail?: string;
}

/** Live `state` snapshot from the SSE stream (api.py). */
export interface StateSnapshot {
  project_status: string;
  current_task_id: string | null;
  tasks: { id: string; title: string; status: TaskStatus; acceptance_criteria: Criterion[] }[];
}

export interface ReplayMeta {
  id: string;
  request: string;
  recorded_at: string;
  provider: string | null;
  model: string | null;
  source: "live" | "cli" | "bench" | "curated";
  note?: string | null;
  final_status?: string | null;
  tasks_planned?: number;
  tasks_done?: number;
  message_count?: number;
  hidden_tests?: { passed: number; total: number } | null;
}

export interface Replay extends ReplayMeta {
  messages: AgentMessage[];
}
