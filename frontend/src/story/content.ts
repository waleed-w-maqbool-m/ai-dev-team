// Story copy. Every claim is true of the repository; the quotes are verbatim
// from the agents' prompts or source files.
import type { AgentId } from "../data/types";

export const TEAM_COPY: Record<AgentId, { job: string; quote: string; source: string }> = {
  pm: {
    job: "Turns a request into tasks with criteria a reviewer could check without guessing.",
    quote: "A criterion is only valid if a reviewer could check it against the code without guessing.",
    source: "prompts/project_manager.md",
  },
  swe: {
    job: "Implements one task at a time. Every file is an explicit change, never prose.",
    quote: "Represent every file you create or modify as an explicit file_changes entry with its full new content.",
    source: "prompts/software_engineer.md",
  },
  testing: {
    job: "The only agent that isn't a language model. It runs what was just written, in a sandbox.",
    quote: "Records real pass/fail evidence — not another LLM judgment.",
    source: "agents/testing.py",
  },
  qa: {
    job: "Judges each acceptance criterion with the Testing Agent's evidence in hand.",
    quote: "Unmoved by confident-sounding explanations that don't match the code in front of you.",
    source: "prompts/qa_reviewer.md",
  },
  docs: {
    job: "Writes the README and changelog once every task is done or set aside.",
    quote: "Document only what was actually implemented and verified.",
    source: "prompts/documentation.md",
  },
};

export const GITHUB_URL = "https://github.com/waleed-w-maqbool-m/ai-dev-team";
