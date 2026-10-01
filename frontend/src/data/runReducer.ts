// Folds the agent message stream into what the scene and HUD render. Live
// runs and replays both go through here, so they can't drift apart. The
// backend's own routing is authoritative; this only mirrors it from the
// messages (plus live `state` snapshots when they exist).
import {
  AGENT_META,
  type AgentId,
  type AgentMessage,
  type Criterion,
  type FileChange,
  type StateSnapshot,
  type TaskStatus,
  type TestCheck,
} from "./types";

export const MAX_REVIEW_ATTEMPTS = 3; // mirrors RunConfig.max_review_iterations

export interface TaskView {
  id: string;
  title: string;
  description: string;
  dependsOn: string[];
  criteria: Criterion[];
  status: TaskStatus;
  attempts: number; // QA rejections so far
}

export type Verdict = "pass" | "fail" | null;

export interface RunEvent {
  index: number;
  agent: AgentId;
  type: AgentMessage["message_type"];
  taskId: string | null;
  title: string;
  verdict: Verdict;
  timestamp: string | null;
}

export type Phase =
  | "idle"
  | "planning"
  | "implementing"
  | "clarifying"
  | "testing"
  | "reviewing"
  | "rejected"
  | "checking"
  | "documenting"
  | "done"
  | "error";

/** A hand-off between stations, which the scene turns into a travelling packet. */
export interface Handoff {
  id: number;
  from: AgentId;
  to: AgentId;
  kind: "forward" | "reject" | "pass" | "clarify";
}

export interface RunView {
  tasks: TaskView[];
  currentTaskId: string | null;
  events: RunEvent[];
  activeAgent: AgentId | null;
  phase: Phase;
  files: Record<string, string>;
  fileOrder: string[];
  summary: string | null;
  lastHandoff: Handoff | null;
  /** Agents that have produced at least one message, for the scene's "warm" glow. */
  touched: AgentId[];
}

export const EMPTY_VIEW: RunView = {
  tasks: [],
  currentTaskId: null,
  events: [],
  activeAgent: null,
  phase: "idle",
  files: {},
  fileOrder: [],
  summary: null,
  lastHandoff: null,
  touched: [],
};

export function agentOf(sender: string): AgentId {
  const hit = (Object.keys(AGENT_META) as AgentId[]).find((a) => AGENT_META[a].sender === sender);
  return hit ?? "pm";
}

function firstRunnable(tasks: TaskView[], preferred?: string | null): TaskView | null {
  const done = new Set(tasks.filter((t) => t.status === "done").map((t) => t.id));
  const runnable = tasks.filter((t) => t.status === "pending" && t.dependsOn.every((d) => done.has(d)));
  return runnable.find((t) => t.id === preferred) ?? runnable[0] ?? null;
}

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

export function applyMessage(view: RunView, msg: AgentMessage, index: number): RunView {
  const agent = agentOf(msg.sender);
  const p = msg.payload ?? {};
  let tasks = view.tasks;
  let currentTaskId = view.currentTaskId;
  let phase: Phase = view.phase;
  let files = view.files;
  let fileOrder = view.fileOrder;
  let summary = view.summary;
  let verdict: Verdict = null;
  let title = "";
  let kind: Handoff["kind"] = "forward";
  const taskId: string | null = (p.task_id as string) ?? currentTaskId;

  const updateTask = (id: string | null, patch: Partial<TaskView>) => {
    if (!id) return;
    tasks = tasks.map((t) => (t.id === id ? { ...t, ...patch } : t));
  };

  switch (msg.message_type) {
    case "plan": {
      tasks = ((p.tasks as any[]) ?? []).map((t) => ({ // eslint-disable-line @typescript-eslint/no-explicit-any
        id: t.id,
        title: t.title,
        description: t.description ?? "",
        dependsOn: t.depends_on ?? [],
        criteria: t.acceptance_criteria ?? [],
        status: "pending" as TaskStatus,
        attempts: 0,
      }));
      currentTaskId = firstRunnable(tasks)?.id ?? null;
      phase = "planning";
      title = `Plan · ${plural(tasks.length, "task")}`;
      break;
    }
    case "clarification_request": {
      phase = "clarifying";
      kind = "clarify";
      title = `${taskId ?? "?"} · asks the PM`;
      break;
    }
    case "implementation": {
      const changes = (p.files_changed as FileChange[]) ?? [];
      files = { ...files };
      fileOrder = [...fileOrder];
      for (const c of changes) {
        if (c.action === "delete") {
          delete files[c.path];
          fileOrder = fileOrder.filter((f) => f !== c.path);
        } else {
          if (!(c.path in files)) fileOrder.push(c.path);
          files[c.path] = c.content;
        }
      }
      updateTask(taskId, { status: "in_review" });
      phase = "implementing";
      title = `${taskId} · ${changes.length ? changes.map((c) => c.path).join(", ") : "no file changes"}`;
      break;
    }
    case "test_report": {
      const checks = (p.checks as TestCheck[]) ?? [];
      const passed = checks.filter((c) => c.passed).length;
      verdict = p.status === "pass" ? "pass" : "fail";
      phase = "testing";
      title = `${taskId} · ${checks.length ? `${passed}/${checks.length} checks` : "nothing to run"}`;
      break;
    }
    case "review": {
      const task = tasks.find((t) => t.id === taskId);
      if (p.status === "pass") {
        verdict = "pass";
        kind = "pass";
        updateTask(taskId, { status: "done" });
        phase = "reviewing";
        title = `${taskId} · QA passed`;
      } else {
        verdict = "fail";
        kind = "reject";
        const attempts = (task?.attempts ?? 0) + 1;
        const capped = attempts >= MAX_REVIEW_ATTEMPTS;
        updateTask(taskId, { attempts, status: capped ? "blocked_needs_human" : "in_progress" });
        phase = "rejected";
        title = capped
          ? `${taskId} · rejected ${attempts}/${MAX_REVIEW_ATTEMPTS}, set aside for a human`
          : `${taskId} · QA rejected (attempt ${attempts} of ${MAX_REVIEW_ATTEMPTS})`;
      }
      break;
    }
    case "status": {
      const next = firstRunnable(tasks, p.next_task_id as string | null);
      currentTaskId = next?.id ?? currentTaskId;
      phase = "checking";
      title = next ? `Next: ${next.id}` : "All tasks resolved";
      break;
    }
    case "documentation": {
      summary = (p.user_summary as string) || null;
      phase = "documenting";
      title = "Docs · README & changelog";
      break;
    }
  }

  const event: RunEvent = {
    index,
    agent,
    type: msg.message_type,
    taskId: msg.message_type === "plan" || msg.message_type === "documentation" ? null : taskId,
    title,
    verdict,
    timestamp: msg.timestamp ?? null,
  };

  const prev = view.activeAgent;
  const lastHandoff: Handoff | null =
    prev && prev !== agent ? { id: index, from: prev, to: agent, kind: kindFor(prev, agent, view, kind) } : view.lastHandoff;

  return {
    tasks,
    currentTaskId,
    events: [...view.events, event],
    activeAgent: agent,
    phase,
    files,
    fileOrder,
    summary,
    lastHandoff,
    touched: view.touched.includes(agent) ? view.touched : [...view.touched, agent],
  };
}

function kindFor(from: AgentId, to: AgentId, before: RunView, current: Handoff["kind"]): Handoff["kind"] {
  // The packet leaving QA carries QA's verdict; one heading back to the PM
  // from the Engineer is a clarification.
  if (from === "qa") return before.phase === "rejected" ? "reject" : "pass";
  if (from === "swe" && to === "pm") return "clarify";
  return current === "clarify" ? "clarify" : "forward";
}

export function applySnapshot(view: RunView, snap: StateSnapshot): RunView {
  const byId = new Map(snap.tasks.map((t) => [t.id, t]));
  return {
    ...view,
    currentTaskId: snap.current_task_id ?? view.currentTaskId,
    tasks: view.tasks.map((t) => {
      const s = byId.get(t.id);
      return s ? { ...t, status: s.status } : t;
    }),
  };
}

export function reduceMessages(messages: AgentMessage[], count = messages.length): RunView {
  let view = EMPTY_VIEW;
  for (let i = 0; i < Math.min(count, messages.length); i++) view = applyMessage(view, messages[i], i);
  return view;
}
