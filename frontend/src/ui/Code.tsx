// Minimal Python highlighting for agent-written code: enough to read it at a
// glance without shipping a full grammar engine to the browser.
import { useMemo } from "react";

const KEYWORDS = new Set(
  "def class return if elif else for while in not and or is import from as with try except finally raise pass break continue lambda yield None True False async await global nonlocal assert del".split(" "),
);
const TOKEN = /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|(\s+|.)/g;

type Tok = { t: string; c?: string };

function tokenize(src: string, python: boolean): Tok[] {
  if (!python) return [{ t: src }];
  const out: Tok[] = [];
  let prevWord = "";
  for (const m of src.matchAll(TOKEN)) {
    const [text, comment, str, num, word] = m;
    if (comment) out.push({ t: text, c: "tok-com" });
    else if (str) out.push({ t: text, c: "tok-str" });
    else if (num) out.push({ t: text, c: "tok-num" });
    else if (word) {
      const c = KEYWORDS.has(word) ? "tok-kw" : prevWord === "def" || prevWord === "class" ? "tok-fn" : undefined;
      out.push({ t: text, c });
      prevWord = word;
      continue;
    } else out.push({ t: text });
    if (text.trim()) prevWord = "";
  }
  return out;
}

export function Code({ source, path }: { source: string; path: string }) {
  const tokens = useMemo(() => tokenize(source, path.endsWith(".py")), [source, path]);
  return (
    <pre className="code">
      <code>
        {tokens.map((tok, i) => (tok.c ? <span key={i} className={tok.c}>{tok.t}</span> : tok.t))}
      </code>
    </pre>
  );
}
