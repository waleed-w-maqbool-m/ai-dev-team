import { useEffect, useMemo, useRef, useState } from "react";

import { navigate } from "../app/router";
import { useUi } from "../app/uiStore";
import { api, type Benchmark } from "../data/api";
import { AGENT_META } from "../data/types";
import { LINE_CODE, LINE_STEPS, TEAM_ORDER, lineStepAt, teamBeatAt } from "../scene/storyScript";
import { MagneticButton } from "../ui/Magnetic";
import { SplitReveal } from "../ui/SplitReveal";
import { GITHUB_URL, TEAM_COPY } from "./content";
import { HeroRibbon } from "./HeroRibbon";
import { useStoryScroll } from "./useStoryScroll";

const pad = (n: number) => String(n).padStart(2, "0");

function Hero() {
  return (
    <div className="hero">
      <HeroRibbon />
      <div className="hero__grid">
        <p className="mono hero__eyebrow">
          <span className="dot" aria-hidden="true" /> LangGraph · Pydantic · Groq / Ollama
        </p>
        <h1 className="hero__title">
          <SplitReveal as="span" className="hero__line">Five agents.</SplitReveal>
          <SplitReveal as="span" className="hero__line" delay={0.12}>
            One <em>deterministic</em> line.
          </SplitReveal>
        </h1>
        <SplitReveal as="p" className="hero__lede" delay={0.35}>
          A Project Manager plans. An Engineer builds. A Testing Agent runs the code. QA judges it with the evidence in
          hand. Docs writes it up. Every handoff is decided by code, not conversation.
        </SplitReveal>
        <div className="hero__ctas">
          <MagneticButton onClick={() => navigate("theater")} cursor="ENTER">
            Watch a run <span aria-hidden="true">→</span>
          </MagneticButton>
          <MagneticButton variant="ghost" href={GITHUB_URL} target="_blank" rel="noreferrer" cursor="CODE">
            Read the code <span aria-hidden="true">↗</span>
          </MagneticButton>
        </div>
      </div>
      <p className="mono dim hero__scroll" aria-hidden="true">Scroll to meet the team ↓</p>
    </div>
  );
}

function Team({ storyTime }: { storyTime: number }) {
  const beat = teamBeatAt(storyTime)?.index ?? (storyTime >= 2 ? TEAM_ORDER.length - 1 : 0);
  const agent = TEAM_ORDER[beat];
  const copy = TEAM_COPY[agent];
  return (
    <div className="team">
      <div className="team__copy">
        <p className="mono dim team__count">
          <span className="accent">{pad(beat + 1)}</span> / {pad(TEAM_ORDER.length)} · The team
        </p>
        <SplitReveal key={`name-${agent}`} as="h2" className="team__name">
          {AGENT_META[agent].name}
        </SplitReveal>
        <SplitReveal key={`job-${agent}`} as="p" className="team__job" delay={0.08}>
          {copy.job}
        </SplitReveal>
        <figure className="team__quote" key={agent}>
          <blockquote className="mono">“{copy.quote}”</blockquote>
          <figcaption className="mono dim">{copy.source}</figcaption>
        </figure>
      </div>
      <ol className="team__rail" aria-label="Agents">
        {TEAM_ORDER.map((a, i) => (
          <li key={a} className="mono" data-active={i === beat || undefined} data-done={i < beat || undefined}>
            {AGENT_META[a].short}
          </li>
        ))}
      </ol>
    </div>
  );
}

function Line({ storyTime }: { storyTime: number }) {
  const at = lineStepAt(storyTime);
  const index = at?.index ?? (storyTime >= 2.94 ? LINE_STEPS.length - 1 : 0);
  const step = LINE_STEPS[index];
  const highlighted = new Set(step.code);
  const tone = step.kind === "reject" ? "fail" : step.kind === "pass" ? "pass" : "accent";
  return (
    <div className="line">
      <div className="line__copy">
        <p className="mono dim">
          The line · step <span className={tone}>{pad(index + 1)}</span> / {pad(LINE_STEPS.length)}
        </p>
        <SplitReveal as="h2" className="line__title" onScroll>
          Routing is <em>code</em>, not conversation.
        </SplitReveal>
        <p className={`line__caption line__caption--${tone}`} aria-live="polite">
          {step.caption}
        </p>
        <div className="line__progress" aria-hidden="true">
          {LINE_STEPS.map((s, i) => (
            <span key={i} data-on={i <= index || undefined} data-kind={s.kind} />
          ))}
        </div>
      </div>
      <figure className="line__code panel">
        <figcaption className="mono dim">graph/routing.py · abridged</figcaption>
        <pre>
          <code>
            {LINE_CODE.map((l, i) => (
              <span key={i} className="code-line" data-hot={highlighted.has(i) || undefined}>
                {l || " "}
                {"\n"}
              </span>
            ))}
          </code>
        </pre>
      </figure>
    </div>
  );
}

function Proof() {
  const [bench, setBench] = useState<Benchmark | null>(null);
  useEffect(() => {
    api.benchmark().then(setBench).catch(() => setBench(null));
  }, []);
  const best = bench?.configs.length
    ? [...bench.configs].sort((a, b) => b.solved / b.runs - a.solved / a.runs)[0]
    : null;

  const facts: { big: string; text: string }[] = [
    { big: "66", text: "hidden test cases in the benchmark. The agents never see them." },
    { big: "59", text: "tests in CI on every push, against both sandbox modes." },
    { big: "3", text: "attempts per task, then it's set aside for a human. Every loop ends." },
    best
      ? { big: `${best.solved}/${best.runs}`, text: `benchmark tasks solved end to end by ${best.model}, scored by hidden tests.` }
      : { big: "—", text: "Benchmark: not run yet. Numbers appear here only once they've been measured." },
  ];

  return (
    <div className="proof">
      <SplitReveal as="h2" className="proof__title" onScroll>
        Trust, <em>measured</em>.
      </SplitReveal>
      <ul className="proof__facts">
        {facts.map((f) => (
          <li key={f.text}>
            <SplitReveal as="span" className="proof__big" onScroll>{f.big}</SplitReveal>
            <SplitReveal as="span" className="proof__text" onScroll delay={0.1}>{f.text}</SplitReveal>
          </li>
        ))}
      </ul>
      <p className="mono dim proof__sandbox">
        Generated code runs in a container: no network · read-only filesystem · no capabilities · non-root · memory, CPU and
        process limits
      </p>
    </div>
  );
}

function Enter() {
  return (
    <div className="enter">
      <SplitReveal as="h2" className="enter__title" onScroll>
        Now watch it <em>work</em>.
      </SplitReveal>
      <p className="enter__lede muted">
        Replay a recorded real run, or start your own against the local backend.
      </p>
      <MagneticButton onClick={() => navigate("theater")} cursor="ENTER">
        Enter the theater <span aria-hidden="true">→</span>
      </MagneticButton>
    </div>
  );
}

export function StoryPage() {
  const hero = useRef<HTMLElement>(null);
  const team = useRef<HTMLElement>(null);
  const line = useRef<HTMLElement>(null);
  const proof = useRef<HTMLElement>(null);
  const enter = useRef<HTMLElement>(null);
  const sections = useMemo(() => ({ hero, team, line, proof, enter }), []);
  const storyTime = useStoryScroll(sections);
  const reduced = useUi((s) => s.reducedMotion);

  return (
    <main id="main" className="story" data-reduced={reduced || undefined}>
      <section ref={hero} className="story__section story__section--hero" aria-label="Introduction">
        <Hero />
      </section>
      <section ref={team} className="story__section story__section--team" aria-label="The team">
        <Team storyTime={storyTime} />
      </section>
      <section ref={line} className="story__section story__section--line" aria-label="How work moves">
        <Line storyTime={storyTime} />
      </section>
      <section ref={proof} className="story__section story__section--proof" aria-label="Proof">
        <Proof />
      </section>
      <section ref={enter} className="story__section story__section--enter" aria-label="Enter the theater">
        <Enter />
      </section>
    </main>
  );
}
