# Creative Brief — AI Dev Team frontend

_Final draft after six discovery rounds (2026-10-01). Awaiting approval before the build._

## Concept
- **One line:** A software team you can watch work, where every handoff is decided by code rather than conversation.
- **Feeling in three words:** Precise. Alive. Accountable.
- **Audience:** recruiters and engineers arriving from GitHub (Story page, public replay site); you, running real jobs (Theater).
- **Primary CTA:** "Watch a run" (enter the Theater). Secondary: "Read the code ↗" (GitHub).

## Decisions
| # | Decision | Choice |
|---|---|---|
| 1 | Surfaces | **Story** (cinematic scroll) → **Theater** (live / replay) + **Runs** library + **Benchmark** page |
| 2 | Agent visualization | **3D studio floor**: five sculptural stations joined by light ribbons; work packets travel between them |
| 3 | Data | **Live** runs via FastAPI SSE + **Replay** of recorded *real* runs, labelled "Recorded run · <date> · <model>". No simulated runs anywhere |
| 4 | Stack | Vite 8 · React 19.3 · TypeScript · R3F 9.8 · drei 10.7 · @react-three/postprocessing 3.1 · three 0.186 · GSAP 3.15 + @gsap/react 2.1 · Lenis 1.3 · `frontend/` → `frontend/dist`, served by FastAPI |
| 5 | Theater layout | Stage-first, docked HUD (see Theater storyboard) |
| 6 | Other pages | About → Story. Run Logs → Runs library (all replayable). Analytics → Benchmark (real results only) |
| 7 | Micro-interactions | Custom cursor (dot + damped ring, morphs into RUN / HOLD ▸▸ / ENTER labels; native cursor on inputs) · magnetic primary buttons |
| 8 | Hosting | Local FastAPI (full app) + static replay-only build on GitHub Pages via CI, linked from the README |
| 9 | Copy | Written by Claude from the real code, prompts and benchmark; every claim true of the repo |
| 10 | Accessibility | Full: `prefers-reduced-motion` **plus** a visible "Reduce motion" toggle; keyboard reach; visible focus; AA contrast; canvas `aria-hidden` with a live text log of agent events |
| 11 | Performance | Must run on this laptop: ≥ 50 fps on Vega 8 at 1080p, ≥ 55 fps on discrete GPUs; auto-degrade DPR → bloom → particles |
| 12 | Providers | Groq only (already supported) |

## Locked references
| Reference | Source / award | Borrow | Avoid | Used in |
|---|---|---|---|---|
| Cerebrium (cerebrium.ai) | Awwwards SOTD, Sep 2026 | Single glowing ribbon arcs on black; click-and-hold | Pink accent, generic light SaaS sections | Handoff ribbons; hold-to-fast-forward in Replay |
| Lusion v3 (lusion.co) | Studio; multiple Awwwards SOTD / Developer awards | 0→100 preloader counter; a 3D path weaving in front of / behind a giant headline | Periwinkle palette | Preloader; Story hero |
| Oryzo AI (oryzo.ai), by Lusion | Awwwards SOTM 2026 | CAD-style dashed bounding box with handles + measurement ticks | Warm cork product photography | Station hover state; active-agent frame in the Theater |

Technique reference (not a visual one): Codrops, "How to Build Cinematic 3D Scroll Experiences with GSAP" (Nov 2025): a pinned, scroll-scrubbed camera through a 3D scene.

## Design tokens
**Palette — Graphite & Signal**
| Token | Hex | Role |
|---|---|---|
| `--bg` | `#07080A` | Page / stage background |
| `--surface` | `#111317` | Panels, plinths |
| `--line` | `rgba(236,234,228,0.09)` | Hairline borders, grid, contours |
| `--text` | `#ECEAE4` | Primary text |
| `--text-muted` | `#9A9890` | Secondary text (AA on `--bg`) |
| `--accent` | `#FF5B1F` | Signal orange: work packets, active agent, primary CTA |
| `--pass` | `#7CE0C3` | QA pass, passing checks |
| `--glow` | `#FFB27A` | Emissive halo |
| `--fail` | `#FF3B4E` | QA rejection, failed checks |

**Type — Instrument Serif + Geist**
| Role | Family | Size / leading | Use |
|---|---|---|---|
| Display | Instrument Serif (regular + italic) | `clamp(56px, 9vw, 168px)` / 0.92 | Story headlines |
| H2 | Instrument Serif | `clamp(40px, 5.5vw, 96px)` / 0.98 | Section titles |
| Body | Geist (variable, 400/500) | 16–18px / 1.55 | Copy, UI |
| Mono | Geist Mono | 11–12px, uppercase, tracking 0.08em | HUD microtype, task ids, telemetry, code |

Italic serif marks the one emphasised word per headline. Layout is deliberately asymmetric: text on a 12-column grid, and the hero headline is left-aligned, never centred.

**Spacing & shape:** 4px base (4 / 8 / 12 / 16 / 24 / 32 / 48 / 72 / 120 / 192). Radii: 2px on panels (engineered, not bubbly), fully round only on the cursor and status dots. 1px hairline borders; no glassmorphism cards, no gradients except emissive falloff.

## Motion tokens — "Precise machine"
| Token | Value | Use |
|---|---|---|
| `ease.enter` | `expo.out`, 0.9–1.2 s | Entrances |
| `ease.camera` | `power3.inOut`, 1.6–2.4 s | Theater camera; scrubbed on Story |
| `stagger.char` / `stagger.line` | 0.035 s / 0.08 s | Split-text reveals |
| `spring.packet` | stiffness 180, damping 22 | Work packets only (the one "physical" thing) |
| `ease.hover` | `power2.out`, 0.25 s | Hover, magnetic return |
| Lenis | `lerp: 0.085` | Story smooth scroll |

**Post-processing (restrained):** selective bloom on emissive only (luminance threshold 0.9, intensity 0.8), grain opacity 0.035, vignette darkness 0.55. No DOF, no chromatic aberration.

## Story storyboard
| # | Section | Scroll | What moves | 3D | Cursor | Into next |
|---|---|---|---|---|---|---|
| 0 | Preloader | — | Mono counter 000→100 bottom-left; the stage's 3D bundle loads behind it | — | — | Counter collapses into the first ribbon |
| 1 | Hero | 0–1 vh | Headline reveals line by line: "Five agents. / One *deterministic* line." The sub-line and CTAs fade up | A light ribbon weaves in front of and behind the headline letters (Lusion); the stage glows faintly below | Stage tilts ±6° toward the cursor; ENTER cursor label on the CTA | Scroll pins; the camera tilts down onto the stage |
| 2 | Team | pinned, 5 beats | One beat per agent: name (serif), its job, and a real line from its prompt (mono) | Camera dollies station to station; the active station's inlay ignites; CAD box (Oryzo) frames it | Hovering any station shows its CAD box | Camera pulls back to the whole line |
| 3 | Line | pinned, scrubbed | Captions in step with the packet; the routing function from `graph/routing.py` reveals line by line, with the branch being taken highlighted | One packet: PM → SWE → TEST (core flashes) → QA (scan beam) → **rejected**: red pulse back along the retry arc → SWE → TEST → QA → pass (mint) → DOCS (plates fan) | — | The scene freezes and dims |
| 4 | Proof | ~1.5 vh | Facts reveal by split-text: 66 hidden tests the agents never see · 59 tests in CI · sandbox: no network, read-only, non-root · benchmark solve rate (only once measured) | The stage recedes behind the type, ribbons slow down | — | Camera dives toward the stage |
| 5 | Enter | 1 vh | "Now watch it work." + magnetic CTA | The dive continues into the Theater's opening framing | RUN label | Route change; the canvas persists |

**Draft copy**
- Hero sub: "A Project Manager plans. An Engineer builds. A Testing Agent runs the code. QA judges it with the evidence in hand. Docs writes it up. Every handoff is decided by code, not conversation."
- Team: PM: "Turns a request into tasks with criteria a reviewer could check without guessing." SWE: "Implements one task at a time. Every file is an explicit change, never prose." TEST: "The only agent that isn't a language model. It runs what was just written." QA: "Unmoved by confident-sounding explanations that don't match the code in front of it." DOCS: "Writes the README and changelog once every task is done or set aside."
- Line: "Routing is code, not conversation." On rejection: "Rejected. Back to the Engineer, attempt 2 of 3." Then: "After three attempts, a task is set aside for a human. Every loop ends."
- Proof heading: "Trust, measured."

## Theater storyboard
Layout: full-bleed stage; top bar with the request field, **Run** (live) and **Replay ▾** (recorded runs); a task strip under it (T1…Tn chips with live status); a right-docked panel showing the active agent's real output (plan / code with syntax highlight / test checks / QA findings / docs); a bottom timeline with one tick per event (seekable in Replay; **hold** to fast-forward ×4); a files drawer with the zip download.

| State | Camera | Stage | HUD |
|---|---|---|---|
| Idle | Wide, slow drift | Dim; stations breathe; ribbons barely visible | Request field focused; example chips |
| Planning | Dolly to PM | PM ring spins up | Tasks split-reveal into the task strip |
| Implementing | Track the packet to SWE | Layers print upward | Code streams into the panel |
| Testing | Close on the reactor | Core flashes once per check (mint / red) | Checks list ticks in, with the sandbox used |
| Review | QA lens | Scan beam sweeps the packet | Findings per criterion; verdict |
| Rejected | Follow the packet back along the retry arc | Red pulse | "Attempt n of 3" |
| Done | Pull back to the full line | Every completed inlay holds a warm glow | Summary card + files |

The active station always carries the CAD frame (Oryzo). A screen-reader-only live region announces each event.

## Runs & Benchmark pages
- **Runs:** table of every recorded run (live runs and benchmark runs): request, model, date, tasks done/blocked, hidden-test score where it exists. Each row offers "Replay in Theater".
- **Benchmark:** the real numbers from `bench/results` (solve rate per config, false "done", per-task grid). Before the first benchmark run it shows an honest "not measured yet" state, never placeholder numbers.

## 3D scene map
**One persistent canvas** behind the DOM for the whole app; the Story camera and the Theater camera are two directors over the same stage.

| Agent | Form | Working state |
|---|---|---|
| Project Manager | Tall monolith with an orbiting ring | Ring spins up while planning or checking |
| Software Engineer | Block extruding thin layers upward | Layers print while writing code |
| Testing Agent | Glass cylinder "reactor" with an inner core | Core flashes per check: mint pass, red fail |
| QA Reviewer | Ring aperture / lens | Scan beam sweeps the packet before the verdict |
| Documentation | Stack of thin plates | Plates fan open like pages |

- **Materials:** matte graphite clay (`#1A1C20`, roughness 0.85) with emissive signal-orange inlays (idle 0.15 → active 2.5); `MeshTransmissionMaterial` only on the reactor; floor `#07080A` with fine contour lines; one key light + rim + environment map; no real-time shadows (baked contact-shadow decal instead).
- **Ribbons:** tube geometry along every real graph edge, including the QA→SWE retry arc and the clarification arc SWE→PM; a flowing emissive shader with additive blending.
- **Packets:** small emissive capsules on a spring along the ribbon curves; red on rejection.
- **Interactions:** whole-stage tilt (damped via `maath`, clamped ±6°, idle breathing); hover lifts a station 4% and snaps the CAD box around it.
- **Mobile:** no post-processing, DPR 1, fewer particles, portrait framing with the line stacked vertically; tap shows a station's CAD box.
- **Fallback:** no WebGL → a designed static poster of the stage (rendered once, offline) plus the full HTML HUD; replays still work as a text timeline.
- **Reduced motion:** Lenis off, no scrub (sections show their end state), no tilt; stage motion slowed ~90%; packets jump between stations with a fade.

## Assumptions & open items
1. **Proof numbers:** only measured numbers appear. The benchmark solve rate shows only after the benchmark runs on your Groq key; until then that line reads "benchmark: not run yet".
2. **First replay:** the one real run log recorded on 2026-08-08 (CSV→JSON, 3 tasks, all passed QA; archived) becomes the first replay and the default on the public site until benchmark runs exist. It ran on the older code without the Testing Agent's sandbox field; the Theater handles missing fields.
3. You didn't pick count-up counters or code typing: proof numbers and the routing code reveal by split-text instead.
4. No click-to-inspect and no drag-orbit (not selected): output lives in the right panel; the CAD box shows on hover only.
5. Station models are built procedurally in code (no external GLB files), which keeps the bundle small and the shapes exactly on-brief.
6. The existing single-file dashboard stays in git history; `api.py` serves `frontend/dist` and keeps `/runs`, `/workspace`, `/download.zip` unchanged, plus a new `/replays` endpoint.
