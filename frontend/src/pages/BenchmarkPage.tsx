import { useEffect, useState } from "react";

import { api, type Benchmark } from "../data/api";
import { SplitReveal } from "../ui/SplitReveal";

const pct = (x: number) => `${Math.round(x * 100)}%`;

export function BenchmarkPage() {
  const [data, setData] = useState<Benchmark | null | "error">(null);
  useEffect(() => {
    api.benchmark().then(setData).catch(() => setData("error"));
  }, []);
  const bench = data && data !== "error" ? data : null;
  const empty = data === "error" || (bench && bench.configs.length === 0);

  return (
    <main id="main" className="page">
      <header className="page-head">
        <p className="mono dim">Benchmark</p>
        <SplitReveal as="h1" className="page-title">Scored by tests the agents <em>never see</em>.</SplitReveal>
        <p className="page-lede">
          {bench?.task_count ?? 12} specified tasks, {bench?.case_count ?? 66} hidden test cases. A task is solved only
          when the generated code passes every one of them. "False done" counts runs where QA approved every task but the
          hidden tests still fail: how often the team's own review was wrong.
        </p>
      </header>

      {data === null && <p className="muted">Loading…</p>}

      {empty && (
        <section className="bench-empty panel page-solid" aria-label="No results yet">
          <p className="serif bench-empty__title">Not measured yet.</p>
          <p className="muted">
            No benchmark runs have been recorded, so there are no numbers to show. This page fills in from real results
            only.
          </p>
          <pre className="code">python -m bench.run --name llama-3.3-70b --provider groq --model llama-3.3-70b-versatile{"\n"}python -m bench.report</pre>
        </section>
      )}

      {bench && bench.configs.length > 0 && (
        <>
          <div className="table-wrap page-solid">
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">Config</th>
                  <th scope="col">Model</th>
                  <th scope="col">Testing Agent</th>
                  <th scope="col">Solved</th>
                  <th scope="col">Hidden tests passed</th>
                  <th scope="col">False "done"</th>
                  <th scope="col">LLM calls / run</th>
                  <th scope="col">Tokens / run</th>
                </tr>
              </thead>
              <tbody>
                {bench.configs.map((c) => (
                  <tr key={c.name}>
                    <td className="mono">{c.name}</td>
                    <td className="mono muted">{c.model}</td>
                    <td>{c.testing_agent}</td>
                    <td><span className="bench-big">{c.solved}/{c.runs}</span> <span className="muted">{pct(c.solved / c.runs)}</span></td>
                    <td>{pct(c.check_rate)}</td>
                    <td>{c.false_done}/{c.claimed}</td>
                    <td className="mono">{c.llm_calls.toFixed(1)}</td>
                    <td className="mono">{(c.tokens / 1000).toFixed(1)}k</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <h2 className="mono dim bench-sub">Per task · hidden tests passed / total</h2>
          <div className="table-wrap page-solid">
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">Task</th>
                  <th scope="col">Difficulty</th>
                  {bench.configs.map((c) => <th key={c.name} scope="col">{c.name}</th>)}
                </tr>
              </thead>
              <tbody>
                {bench.per_task.map((t) => (
                  <tr key={t.task}>
                    <td className="mono">{t.task}</td>
                    <td className="muted">{t.difficulty}</td>
                    {bench.configs.map((c) => <td key={c.name} className="mono">{t.results[c.name] ?? "—"}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}
