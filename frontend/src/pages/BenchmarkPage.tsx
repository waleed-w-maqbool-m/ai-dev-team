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
        <p className="bench-status page-solid" role="status">
          <span className="tag">Results</span> Awaiting the first benchmark run. Scores appear here once real runs have
          been measured; nothing is estimated.
        </p>
      )}

      {bench && bench.suite?.length > 0 && (
        <section className="bench-suite" aria-labelledby="suite-title">
          <h2 id="suite-title" className="mono dim bench-sub">The suite · {bench.task_count} tasks · {bench.case_count} hidden tests</h2>
          <ol className="suite-list page-solid">
            {bench.suite.map((t, i) => (
              <li key={t.task} className="suite-item">
                <span className="mono dim suite-item__n">{String(i + 1).padStart(2, "0")}</span>
                <div className="suite-item__body">
                  <p className="suite-item__title">{t.title}</p>
                  <details>
                    <summary className="mono">The exact request</summary>
                    <p className="suite-item__request">{t.request}</p>
                  </details>
                </div>
                <span className={`tag suite-item__difficulty suite-item__difficulty--${t.difficulty}`}>{t.difficulty}</span>
                <span className="mono suite-item__cases">{t.cases} tests</span>
              </li>
            ))}
          </ol>
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
