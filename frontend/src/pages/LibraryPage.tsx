import { useEffect, useState } from "react";

import { navigate } from "../app/router";
import { api } from "../data/api";
import type { ReplayMeta } from "../data/types";
import { SplitReveal } from "../ui/SplitReveal";

const SOURCE_LABEL: Record<ReplayMeta["source"], string> = {
  live: "Web console",
  cli: "CLI",
  bench: "Benchmark",
  curated: "Archive",
};

export function LibraryPage() {
  const [runs, setRuns] = useState<ReplayMeta[] | null>(null);
  useEffect(() => {
    api.replays().then(setRuns).catch(() => setRuns([]));
  }, []);

  return (
    <main id="main" className="page">
      <header className="page-head">
        <p className="mono dim">Runs library</p>
        <SplitReveal as="h1" className="page-title">Every run, <em>replayable</em>.</SplitReveal>
        <p className="page-lede">
          Each row is a real recorded run: the exact agent messages, played back through the same stage. Nothing here is
          simulated.
        </p>
      </header>
      <div className="table-wrap page-solid">
        <table className="data">
          <thead>
            <tr>
              <th scope="col">Recorded</th>
              <th scope="col">Request</th>
              <th scope="col">Model</th>
              <th scope="col">Tasks</th>
              <th scope="col">Hidden tests</th>
              <th scope="col">Source</th>
              <th scope="col"><span className="sr-only">Action</span></th>
            </tr>
          </thead>
          <tbody>
            {runs === null && (
              <tr><td colSpan={7} className="muted">Loading…</td></tr>
            )}
            {runs?.length === 0 && (
              <tr><td colSpan={7} className="muted">No recorded runs yet. Run one from the Theater with the local backend.</td></tr>
            )}
            {runs?.map((r) => (
              <tr key={r.id}>
                <td className="mono" data-label="Recorded">{new Date(r.recorded_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</td>
                <td className="library__request">
                  {r.request}
                  {r.note && <p className="mono dim library__note">{r.note}</p>}
                </td>
                <td className="mono muted" data-label="Model">{r.model ?? "not recorded"}</td>
                <td className="mono" data-label="Tasks done">
                  {r.tasks_done ?? "?"}/{r.tasks_planned ?? "?"}
                </td>
                <td data-label="Hidden tests">
                  {r.hidden_tests ? (
                    <span className={`tag ${r.hidden_tests.passed === r.hidden_tests.total ? "tag--pass" : "tag--fail"}`}>
                      {r.hidden_tests.passed}/{r.hidden_tests.total}
                    </span>
                  ) : (
                    <span className="dim">—</span>
                  )}
                </td>
                <td data-label="Source"><span className="tag">{SOURCE_LABEL[r.source]}</span></td>
                <td>
                  <button type="button" className="btn btn--ghost btn--sm" data-cursor="REPLAY" onClick={() => navigate("theater", `?replay=${encodeURIComponent(r.id)}`)}>
                    <span className="btn__fill" aria-hidden="true" />
                    Replay <span aria-hidden="true">→</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
