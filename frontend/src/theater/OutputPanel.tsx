// The right-docked panel: the real output behind the selected (or latest)
// event — plan, code, test checks, QA findings, PM decision, docs — or a file.
import { useRun } from "../data/runStore";
import { AGENT_META, type AgentMessage, type TestCheck } from "../data/types";
import { Code } from "../ui/Code";

function Plan({ p }: { p: AgentMessage["payload"] }) {
  return (
    <>
      {p.overview && <p className="op__lede">{p.overview}</p>}
      <ol className="op__tasks">
        {(p.tasks ?? []).map((t: any) => ( // eslint-disable-line @typescript-eslint/no-explicit-any
          <li key={t.id}>
            <p><span className="tag tag--accent">{t.id}</span> {t.title}</p>
            {t.depends_on?.length > 0 && <p className="mono dim">after {t.depends_on.join(", ")}</p>}
            <ul className="op__criteria">
              {(t.acceptance_criteria ?? []).map((c: any) => <li key={c.id}>{c.description}</li>)} {/* eslint-disable-line @typescript-eslint/no-explicit-any */}
            </ul>
          </li>
        ))}
      </ol>
    </>
  );
}

function Implementation({ p }: { p: AgentMessage["payload"] }) {
  const files = (p.files_changed ?? []) as { path: string; action: string; content: string }[];
  return (
    <>
      {p.summary && <p className="op__lede">{p.summary}</p>}
      {files.map((f) => (
        <div key={f.path} className="op__file">
          <p className="mono op__file-name">
            <span className="tag">{f.action}</span> {f.path}
          </p>
          {f.action !== "delete" && <Code source={f.content} path={f.path} />}
        </div>
      ))}
    </>
  );
}

function TestReport({ p }: { p: AgentMessage["payload"] }) {
  const checks = (p.checks ?? []) as TestCheck[];
  return (
    <>
      <p className="op__lede">
        {p.summary}
        {p.sandbox && <span className="mono dim"> · ran in {p.sandbox === "docker" ? "Docker sandbox" : "host subprocess"}</span>}
      </p>
      <ul className="op__checks">
        {checks.map((c, i) => (
          <li key={i}>
            <span className={`tag ${c.passed ? "tag--pass" : "tag--fail"}`}>{c.passed ? "pass" : "fail"}</span>
            <span className="mono">{c.check}</span> <span className="muted">{c.file}</span>
            {c.detail && <pre className="op__detail">{c.detail}</pre>}
          </li>
        ))}
      </ul>
    </>
  );
}

function Review({ p }: { p: AgentMessage["payload"] }) {
  const pass = p.status === "pass";
  return (
    <>
      <p className={`op__verdict ${pass ? "pass" : "fail"}`}>{pass ? "Passed" : "Sent back"}</p>
      {p.summary && <p className="op__lede">{p.summary}</p>}
      <ul className="op__checks">
        {(p.findings ?? []).map((f: any) => ( // eslint-disable-line @typescript-eslint/no-explicit-any
          <li key={f.criterion_id}>
            <span className={`tag ${f.met ? "tag--pass" : "tag--fail"}`}>{f.met ? "met" : "not met"}</span>
            <span className="mono">{f.criterion_id}</span> <span className="muted">{f.note}</span>
          </li>
        ))}
      </ul>
      {(p.required_fixes ?? []).length > 0 && (
        <>
          <p className="mono dim op__sub">Required fixes</p>
          <ol className="op__fixes">
            {p.required_fixes.map((f: string, i: number) => <li key={i}>{f}</li>)}
          </ol>
        </>
      )}
    </>
  );
}

function Status({ p }: { p: AgentMessage["payload"] }) {
  return (
    <>
      <p className="op__lede">
        {p.next_task_id ? <>Next task: <span className="tag tag--accent">{p.next_task_id}</span></> : `Project status: ${p.project_status}`}
      </p>
      {p.notes && <p className="muted">{p.notes}</p>}
      <p className="mono dim op__note">
        The PM's choice is only a preference: the pipeline checks it against the dependency graph before acting on it.
      </p>
    </>
  );
}

function Docs({ p }: { p: AgentMessage["payload"] }) {
  return (
    <>
      {p.user_summary && <p className="op__lede">{p.user_summary}</p>}
      {(p.changelog_entries ?? []).length > 0 && (
        <>
          <p className="mono dim op__sub">Changelog</p>
          <ul className="op__fixes">{p.changelog_entries.map((c: string, i: number) => <li key={i}>{c}</li>)}</ul>
        </>
      )}
      {p.readme_updates && (
        <>
          <p className="mono dim op__sub">README</p>
          <pre className="op__detail op__detail--plain">{p.readme_updates}</pre>
        </>
      )}
    </>
  );
}

function Clarification({ p }: { p: AgentMessage["payload"] }) {
  return <p className="op__lede">“{p.question}”</p>;
}

const RENDER: Record<AgentMessage["message_type"], (props: { p: AgentMessage["payload"] }) => React.ReactElement> = {
  plan: Plan,
  implementation: Implementation,
  test_report: TestReport,
  review: Review,
  status: Status,
  documentation: Docs,
  clarification_request: Clarification,
};

export function OutputPanel({ selected, file, onClearFile }: { selected: number | null; file: string | null; onClearFile: () => void }) {
  const messages = useRun((s) => s.messages);
  const cursor = useRun((s) => s.cursor);
  const view = useRun((s) => s.view);
  const files = view.files;

  if (file && files[file] !== undefined) {
    return (
      <section className="panel op" aria-label={`File ${file}`}>
        <header className="op__head">
          <p className="mono dim">File</p>
          <h2 className="op__title">{file}</h2>
          <button type="button" className="mono op__close" onClick={onClearFile}>Back to output</button>
        </header>
        <div className="op__body"><Code source={files[file]} path={file} /></div>
      </section>
    );
  }

  const index = selected !== null && selected < cursor ? selected : cursor - 1;
  const msg = index >= 0 ? messages[index] : null;
  const event = index >= 0 ? view.events[index] : null;
  if (!msg || !event) {
    return (
      <section className="panel op op--empty" aria-label="Agent output">
        <p className="mono dim">Agent output</p>
        <p className="muted">Each agent's real output appears here as it works: the plan, the code, the test report, QA's findings.</p>
      </section>
    );
  }
  const Body = RENDER[msg.message_type];
  return (
    <section className="panel op" aria-label={`${AGENT_META[event.agent].name} output`}>
      <header className="op__head">
        <p className="mono dim">
          {String(index + 1).padStart(2, "0")} · {AGENT_META[event.agent].name}
        </p>
        <h2 className="op__title">{event.title}</h2>
      </header>
      <div className="op__body">
        <Body p={msg.payload} />
      </div>
    </section>
  );
}
