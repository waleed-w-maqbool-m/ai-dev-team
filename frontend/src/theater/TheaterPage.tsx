import { useEffect, useState } from "react";

import { hrefFor, navigate, queryParam } from "../app/router";
import { api, type Health } from "../data/api";
import { useRun } from "../data/runStore";
import { AGENT_META } from "../data/types";
import { MagneticButton } from "../ui/Magnetic";
import { OutputPanel } from "./OutputPanel";
import { Timeline } from "./Timeline";

const STATUS_LABEL: Record<string, string> = {
  pending: "queued",
  in_progress: "in progress",
  in_review: "in review",
  done: "done",
  blocked_needs_human: "needs a human",
};

// Requests sized for what the pipeline does well: one small, testable tool
// with a few clear tasks, standard library only (the Docker sandbox has no
// third-party packages).
const EXAMPLE_REQUESTS = [
  "Build a cron expression parser: a library that validates standard 5-field cron expressions, and a CLI that explains one in plain English and prints its next 5 run times.",
  "Build a token-bucket rate limiter library, plus a CLI that replays a request log and reports which requests would have been throttled.",
  "Build a Markdown table-of-contents generator: a CLI that reads a .md file, builds a nested TOC with GitHub-style anchor links, and inserts it between <!-- toc --> markers.",
  "Build a dependency-graph resolver: read packages and their dependencies from a JSON file, print a valid install order, and report any cycles clearly.",
];

function TopBar({ health }: { health: Health }) {
  const { source, startLive, liveStatus, error } = useRun();
  const [draft, setDraft] = useState(EXAMPLE_REQUESTS[0]);
  const busy = source === "live" && (liveStatus === "connecting" || liveStatus === "streaming");

  return (
    <div className="topbar panel">
      <form
        className="topbar__form"
        onSubmit={(e) => {
          e.preventDefault();
          if (health.live && draft.trim() && !busy) startLive(draft.trim());
        }}
      >
        <label className="sr-only" htmlFor="request">What should the team build?</label>
        <input
          id="request"
          className="topbar__input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          readOnly={busy}
          placeholder="Describe a small CLI tool or library…"
          autoComplete="off"
          list="request-examples"
        />
        <datalist id="request-examples">
          {EXAMPLE_REQUESTS.map((r) => <option key={r} value={r} />)}
        </datalist>
        <MagneticButton type="submit" size="sm" disabled={!health.live || busy} cursor="RUN" title={health.live ? undefined : "Live runs need the local backend (python api.py) and an API key."}>
          {busy ? "Running…" : "Run live"}
        </MagneticButton>
      </form>
      {/* Choosing a recording lives on the Runs page; here one line says
          what's playing and links there. */}
      <p className="topbar__status mono" role="status">
        {source === "replay" && (
          <>
            <span className="tag">Recorded run</span>{" "}
            <a
              className="topbar__runs-link"
              href={hrefFor("library")}
              onClick={(e) => {
                e.preventDefault();
                navigate("library");
              }}
            >
              All runs →
            </a>
          </>
        )}
        {source === "live" && <><span className="tag tag--accent">Live</span> {health.provider} · {health.model} · {liveStatus}</>}
        {error && <span className="fail"> {error}</span>}
      </p>
    </div>
  );
}

function TaskStrip() {
  const tasks = useRun((s) => s.view.tasks);
  const current = useRun((s) => s.view.currentTaskId);
  if (!tasks.length) return null;
  return (
    <ol className="taskstrip" aria-label="Tasks">
      {tasks.map((t) => (
        <li key={t.id} className="taskchip panel" data-status={t.status} data-current={t.id === current || undefined}>
          <span className="taskchip__dot" aria-hidden="true" />
          <span className="mono">{t.id}</span>
          <span className="taskchip__title">{t.title}</span>
          <span className="mono dim taskchip__status">
            {STATUS_LABEL[t.status]}
            {t.attempts > 0 && t.status !== "done" ? ` · ${t.attempts}/3` : ""}
          </span>
        </li>
      ))}
    </ol>
  );
}

function FilesDrawer({ onOpen, live }: { onOpen: (path: string) => void; live: boolean }) {
  const order = useRun((s) => s.view.fileOrder);
  const source = useRun((s) => s.source);
  const [open, setOpen] = useState(false);
  if (!order.length) return null;
  return (
    <div className="files panel" data-open={open || undefined}>
      <button type="button" className="mono files__toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
        Files · {order.length}
      </button>
      {open && (
        <div className="files__body">
          <ul>
            {order.map((f) => (
              <li key={f}><button type="button" className="mono" onClick={() => onOpen(f)}>{f}</button></li>
            ))}
          </ul>
          {live && source === "live" && (
            <a className="mono files__zip" href={api.zipUrl(order, "ai-dev-team-run")}>Download .zip</a>
          )}
        </div>
      )}
    </div>
  );
}

/** Text equivalent of the stage for screen readers. */
function LiveLog() {
  const last = useRun((s) => s.view.events[s.view.events.length - 1]);
  return (
    <p className="sr-only" aria-live="polite">
      {last ? `${AGENT_META[last.agent].name}: ${last.title}` : ""}
    </p>
  );
}

export function TheaterPage() {
  const [health, setHealth] = useState<Health>({ live: false });
  const [selected, setSelected] = useState<number | null>(null);
  const [file, setFile] = useState<string | null>(null);
  const source = useRun((s) => s.source);
  const summary = useRun((s) => s.view.summary);
  const phase = useRun((s) => s.view.phase);

  useEffect(() => {
    api.health().then(setHealth);
    // Plays the requested recording (from the Runs page), else the newest.
    api.replays().then((list) => {
      const wanted = queryParam("replay");
      const pick = list.find((r) => r.id === wanted) ?? list[0];
      if (pick && useRun.getState().source === "none") useRun.getState().loadReplay(pick.id);
    }).catch(() => {});
  }, []);

  useEffect(() => setSelected(null), [source]);

  return (
    // A grid, not absolutely positioned boxes: the HUD stacks in flow, so
    // a taller top bar or a long summary pushes things down instead of
    // landing on top of them, at any screen height.
    <main id="main" className="theater">
      <h1 className="sr-only">Agent Theater</h1>
      <div className="theater__left">
        <TopBar health={health} />
        <TaskStrip />
        <div className="theater__dock">
          {phase === "done" && summary && (
            <div className="theater__summary panel">
              <p className="mono dim">Run complete</p>
              <p>{summary}</p>
            </div>
          )}
          <FilesDrawer onOpen={setFile} live={health.live} />
        </div>
      </div>
      <OutputPanel selected={selected} file={file} onClearFile={() => setFile(null)} />
      <Timeline selected={selected} onSelect={setSelected} />
      <LiveLog />
    </main>
  );
}
