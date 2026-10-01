// The Story page's choreography, shared by the 3D director and the DOM
// captions so they can never drift apart. "Story time" runs 0..5: one unit
// per section (hero, team, line, proof, enter), written by ScrollTrigger.
import type { AgentId } from "../data/types";
import type { EdgeKey } from "./layout";

export const TEAM_ORDER: AgentId[] = ["pm", "swe", "testing", "qa", "docs"];

export interface LineStep {
  edge: EdgeKey;
  kind: "forward" | "reject" | "pass";
  /** Caption shown while this step plays. */
  caption: string;
  /** Lines of the routing excerpt (see LINE_CODE) to highlight. */
  code: number[];
  /** What the destination station does on arrival. */
  arrive?: { agent: AgentId; result: "pass" | "fail" };
}

// One packet's real journey through the graph, including a QA rejection.
export const LINE_STEPS: LineStep[] = [
  { edge: "pm>swe", kind: "forward", caption: "The PM hands T1 to the Engineer, with acceptance criteria attached.", code: [0, 1] },
  { edge: "swe>testing", kind: "forward", caption: "Code written. The Testing Agent runs it: parse, import, smoke-run.", code: [3, 6], arrive: { agent: "testing", result: "pass" } },
  { edge: "testing>qa", kind: "forward", caption: "QA reviews the code against each criterion, with the test report in hand.", code: [6], arrive: { agent: "qa", result: "fail" } },
  { edge: "qa>swe", kind: "reject", caption: "Rejected. Back to the Engineer: attempt 2 of 3.", code: [8, 10, 11] },
  { edge: "swe>testing", kind: "forward", caption: "Fixed. Run again.", code: [3, 6], arrive: { agent: "testing", result: "pass" } },
  { edge: "testing>qa", kind: "forward", caption: "Every criterion met.", code: [6], arrive: { agent: "qa", result: "pass" } },
  { edge: "qa>pm", kind: "pass", caption: "Back to the PM, who picks the next runnable task, or calls it done.", code: [8, 12] },
  { edge: "pm>docs", kind: "forward", caption: "Nothing left to run. Documentation writes it up.", code: [] },
];

// Abridged from graph/routing.py — the real functions that decide every hop.
export const LINE_CODE = [
  "def route_after_pm_plan(state):",
  '    return "swe" if state.current_task_id else "docs"',
  "",
  "def route_after_swe(state):",
  "    if task.status == blocked_needs_human: return \"pm_check\"",
  "    if state.project_status == blocked_on_clarification: return \"pm_plan\"",
  '    return "testing"          # testing -> qa, always',
  "",
  "def route_after_qa(state):",
  "    # qa_node already applied the retry cap",
  '    if task.status.value == "in_progress":',
  '        return "swe"          # failed, under the cap',
  '    return "pm_check"         # done, or set aside for a human',
];

/** Story-time window inside the Line section where the packet travels. */
export const LINE_START = 2.08;
export const LINE_END = 2.94;

export function lineStepAt(storyTime: number): { index: number; t: number } | null {
  if (storyTime < LINE_START || storyTime >= LINE_END) return null;
  const span = (LINE_END - LINE_START) / LINE_STEPS.length;
  const index = Math.min(LINE_STEPS.length - 1, Math.floor((storyTime - LINE_START) / span));
  return { index, t: (storyTime - LINE_START - index * span) / span };
}

export function teamBeatAt(storyTime: number): { index: number; t: number } | null {
  if (storyTime < 1 || storyTime >= 2) return null;
  const x = (storyTime - 1) * TEAM_ORDER.length;
  const index = Math.min(TEAM_ORDER.length - 1, Math.floor(x));
  return { index, t: x - index };
}
