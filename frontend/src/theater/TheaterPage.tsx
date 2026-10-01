import { useEffect, useState } from "react";

import { queryParam } from "../app/router";
import { api, type Health } from "../data/api";
import { useRun } from "../data/runStore";
import { AGENT_META, type ReplayMeta } from "../data/types";
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

function formatDate(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function TopBar({ health, replays }: { health: Health; replays: ReplayMeta[] }) {
  const { source, replay, request, startLive, loadReplay, liveStatus, error } = useRun();
  const [draft, setDraft] = useState("Build a CLI tool that converts CSV files to JSON.");
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
        />
        <MagneticButton type="submit" size="sm" disabled={!health.live || busy} cursor="RUN" title={health.live ? undefined : "Live runs need the local backend (python api.py) and an API key."}>
          {busy ? "Running…" : "Run live"}
        </MagneticButton>
      </form>
      <div className="topbar__replay">
        <label className="mono dim" htmlFor="replay-pick">Replay</label>
        <select
          id="replay-pick"
          value={source === "replay" ? replay?.id : ""}
          onChange={(e) => e.target.value && loadReplay(e.target.value)}
        >
          {source !== "replay" && <option value="">Choose a recorded run…</option>}
          {replays.map((r) => (
            <option key={r.id} value={r.id}>
              {formatDate(r.recorded_at)} · {r.request.slice(0, 48)}
            </option>
          ))}
        </select>
      </div>
      <p className="topbar__status mono" role="status">
        {source === "replay" && replay && (
          <>
            <span className="tag">Recorded run</span> {formatDate(replay.recorded_at)} · {replay.model ?? "model not recorded"} · <span className="muted">“{request}”</span>
          </>
        )}
        {source === "live" && <><span className="tag tag--accent">Live</span> {health.provider} · {health.model} · {liveStatus}</>}
        {source === "none" && !health.live && <span className="dim">Live runs need the local backend. Recorded runs play here.</span>}
        {error && <span className="fail"> {error}</span>}
      </p>
      {source === "replay" && replay?.note && <p className="topbar__note mono dim">{replay.note}</p>}
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
  const [replays, setReplays] = useState<ReplayMeta[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [file, setFile] = useState<string | null>(null);
  const source = useRun((s) => s.source);
  const summary = useRun((s) => s.view.summary);
  const phase = useRun((s) => s.view.phase);

  useEffect(() => {
    api.health().then(setHealth);
    api.replays().then((list) => {
      setReplays(list);
      const wanted = queryParam("replay");
      const pick = list.find((r) => r.id === wanted) ?? list[0];
      if (pick && useRun.getState().source === "none") useRun.getState().loadReplay(pick.id);
    }).catch(() => setReplays([]));
  }, []);

  useEffect(() => setSelected(null), [source]);

  return (
    <main id="main" className="theater">
      <h1 className="sr-only">Agent Theater</h1>
      <TopBar health={health} replays={replays} />
      <TaskStrip />
      <OutputPanel selected={selected} file={file} onClearFile={() => setFile(null)} />
      {phase === "done" && summary && (
        <div className="theater__summary panel">
          <p className="mono dim">Run complete</p>
          <p>{summary}</p>
        </div>
      )}
      <FilesDrawer onOpen={setFile} live={health.live} />
      <Timeline selected={selected} onSelect={setSelected} />
      <LiveLog />
    </main>
  );
}
