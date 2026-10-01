// One tick per agent event. In a replay you can click a tick to jump there,
// and press-and-hold the fast-forward control to run at 4×.
import { useRef } from "react";

import { useRun } from "../data/runStore";
import { agentOf } from "../data/runReducer";
import { AGENT_META } from "../data/types";

export function Timeline({ selected, onSelect }: { selected: number | null; onSelect: (i: number | null) => void }) {
  const { source, messages, cursor, view, playing, play, pause, seek, setSpeed, speed } = useRun();
  const holding = useRef(false);
  const ticks = useRef<(HTMLButtonElement | null)[]>([]);
  const replay = source === "replay";
  const total = replay ? messages.length : Math.max(view.events.length, 1);
  const focusIndex = selected ?? cursor - 1;

  const startHold = () => {
    if (!replay) return;
    holding.current = true;
    setSpeed(4);
    if (!playing) play();
  };
  const endHold = () => {
    if (!holding.current) return;
    holding.current = false;
    setSpeed(1);
  };

  return (
    <div className="timeline panel" role="group" aria-label="Run timeline">
      <div className="timeline__controls">
        {replay && (
          <>
            <button type="button" className="tl-btn" onClick={() => (playing ? pause() : play())} aria-label={playing ? "Pause replay" : "Play replay"} data-cursor={playing ? "PAUSE" : "PLAY"}>
              {playing ? "❚❚" : "▶"}
            </button>
            <button
              type="button"
              className="tl-btn tl-btn--hold"
              aria-label="Hold to fast-forward at 4×"
              data-cursor="HOLD ▸▸"
              data-active={speed > 1 || undefined}
              onPointerDown={startHold}
              onPointerUp={endHold}
              onPointerLeave={endHold}
              onKeyDown={(e) => (e.key === " " || e.key === "Enter") && !e.repeat && startHold()}
              onKeyUp={endHold}
            >
              ▸▸ <span className="mono">hold</span>
            </button>
          </>
        )}
        <p className="mono dim timeline__count" aria-live="off">
          {String(cursor).padStart(2, "0")} / {String(replay ? messages.length : view.events.length).padStart(2, "0")} events
        </p>
      </div>
      {/* One tab stop for the whole track; arrows / Home / End move between
          events (roving tabindex), so keyboard users don't tab through 30 ticks. */}
      <ol
        className="timeline__track"
        aria-label="Events"
        onKeyDown={(ev) => {
          const step = { ArrowRight: 1, ArrowLeft: -1, Home: -Infinity, End: Infinity }[ev.key];
          if (step === undefined) return;
          ev.preventDefault();
          const last = Math.max(0, (replay ? total : view.events.length) - 1);
          const next = Math.min(last, Math.max(0, (focusIndex === -1 ? 0 : focusIndex) + step));
          ticks.current[next]?.focus();
          ticks.current[next]?.click();
        }}
      >
        {Array.from({ length: total }, (_, i) => {
          const e = view.events[i];
          const reached = i < cursor;
          return (
            <li key={i}>
              <button
                ref={(b) => { ticks.current[i] = b; }}
                tabIndex={i === Math.max(0, focusIndex) ? 0 : -1}
                type="button"
                className="tick"
                data-agent={e?.agent ?? (messages[i] ? agentOf(messages[i].sender) : undefined)}
                data-verdict={e?.verdict ?? undefined}
                data-reached={reached || undefined}
                data-selected={selected === i || undefined}
                disabled={!reached && !replay}
                aria-label={e ? `${i + 1}: ${AGENT_META[e.agent].name}, ${e.title}` : `Event ${i + 1} (not reached yet)`}
                onClick={() => {
                  if (replay && !reached) {
                    seek(i + 1);
                    onSelect(null);
                  } else onSelect(selected === i ? null : i);
                }}
              />
            </li>
          );
        })}
      </ol>
    </div>
  );
}
