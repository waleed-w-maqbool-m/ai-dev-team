import { create } from "zustand";

import { api } from "./api";
import { applySnapshot, reduceMessages, type RunView, EMPTY_VIEW } from "./runReducer";
import type { AgentMessage, Replay, ReplayMeta, StateSnapshot } from "./types";

type Source = "none" | "live" | "replay";

interface RunState {
  source: Source;
  request: string;
  replay: ReplayMeta | null;
  messages: AgentMessage[];
  /** How many messages are applied (replays reveal them over time). */
  cursor: number;
  view: RunView;
  snapshot: StateSnapshot | null;
  playing: boolean;
  speed: number;
  liveStatus: "idle" | "connecting" | "streaming" | "done" | "error";
  error: string | null;

  startLive: (request: string) => void;
  loadReplay: (id: string, autoplay?: boolean) => Promise<void>;
  play: () => void;
  pause: () => void;
  seek: (cursor: number) => void;
  setSpeed: (speed: number) => void;
  reset: () => void;
}

let source: EventSource | null = null;
let timer: number | null = null;

function stopTimers() {
  if (timer !== null) window.clearTimeout(timer);
  timer = null;
  source?.close();
  source = null;
}

/** Pause before revealing message `i` of a replay. Real gaps between agent
 * calls range from seconds to minutes, so they're compressed into a band
 * that's watchable but keeps the rhythm of the real run. */
export function replayDelay(messages: AgentMessage[], i: number): number {
  if (i === 0) return 900;
  const a = Date.parse(messages[i - 1]?.timestamp ?? "");
  const b = Date.parse(messages[i]?.timestamp ?? "");
  const real = Number.isFinite(a) && Number.isFinite(b) ? Math.max(0, b - a) : 3000;
  return Math.min(4200, Math.max(1700, real * 0.12));
}

export const useRun = create<RunState>((set, get) => {
  const derive = (messages: AgentMessage[], cursor: number, snapshot: StateSnapshot | null) => {
    const view = reduceMessages(messages, cursor);
    return snapshot ? applySnapshot(view, snapshot) : view;
  };

  const tick = () => {
    const { messages, cursor, playing, speed, source: src } = get();
    if (src !== "replay" || !playing) return;
    if (cursor >= messages.length) {
      set({ playing: false });
      return;
    }
    timer = window.setTimeout(() => {
      const next = get().cursor + 1;
      set({ cursor: next, view: derive(get().messages, next, null) });
      tick();
    }, replayDelay(messages, cursor) / speed);
  };

  return {
    source: "none",
    request: "",
    replay: null,
    messages: [],
    cursor: 0,
    view: EMPTY_VIEW,
    snapshot: null,
    playing: false,
    speed: 1,
    liveStatus: "idle",
    error: null,

    startLive: (request) => {
      stopTimers();
      set({
        source: "live", request, replay: null, messages: [], cursor: 0, view: EMPTY_VIEW,
        snapshot: null, playing: true, liveStatus: "connecting", error: null,
      });
      source = new EventSource(api.liveRunUrl(request));
      source.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === "message") {
          const messages = [...get().messages, {
            sender: data.sender, message_type: data.message_type, payload: data.payload,
            timestamp: data.timestamp ?? new Date().toISOString(),
          }];
          set({ messages, cursor: messages.length, liveStatus: "streaming", view: derive(messages, messages.length, get().snapshot) });
        } else if (data.type === "state") {
          const snapshot = data as StateSnapshot;
          set({ snapshot, view: applySnapshot(get().view, snapshot) });
        } else if (data.type === "done") {
          set({ liveStatus: "done", playing: false, view: { ...get().view, phase: "done", activeAgent: null } });
          stopTimers();
        } else if (data.type === "error") {
          set({ liveStatus: "error", playing: false, error: data.message, view: { ...get().view, phase: "error" } });
          stopTimers();
        }
      };
      source.onerror = () => {
        if (get().liveStatus === "done") return;
        set({ liveStatus: "error", playing: false, error: "Lost the connection to the local backend." });
        stopTimers();
      };
    },

    loadReplay: async (id, autoplay = true) => {
      stopTimers();
      const replay: Replay = await api.replay(id);
      const { messages, ...meta } = replay;
      set({
        source: "replay", request: replay.request, replay: meta, messages, cursor: 0,
        view: EMPTY_VIEW, snapshot: null, playing: false, liveStatus: "idle", error: null,
      });
      if (autoplay) get().play();
    },

    play: () => {
      const { source: src, cursor, messages } = get();
      if (src !== "replay") return;
      if (timer !== null) window.clearTimeout(timer);
      if (cursor >= messages.length) set({ cursor: 0, view: EMPTY_VIEW });
      set({ playing: true });
      tick();
    },

    pause: () => {
      if (timer !== null) window.clearTimeout(timer);
      timer = null;
      set({ playing: false });
    },

    seek: (cursor) => {
      if (get().source !== "replay") return;
      const clamped = Math.max(0, Math.min(cursor, get().messages.length));
      if (timer !== null) window.clearTimeout(timer);
      set({ cursor: clamped, view: derive(get().messages, clamped, null) });
      if (clamped >= get().messages.length) set({ view: { ...get().view, phase: "done", activeAgent: null } });
      if (get().playing) tick();
    },

    setSpeed: (speed) => {
      set({ speed });
      if (get().playing && get().source === "replay") {
        if (timer !== null) window.clearTimeout(timer);
        tick();
      }
    },

    reset: () => {
      stopTimers();
      set({ source: "none", replay: null, messages: [], cursor: 0, view: EMPTY_VIEW, playing: false, liveStatus: "idle", error: null });
    },
  };
});

/** Marks a finished replay as done (the scene pulls back). */
useRun.subscribe((s, prev) => {
  if (s.source === "replay" && s.cursor === s.messages.length && s.messages.length > 0 && prev.cursor !== s.cursor) {
    useRun.setState({ view: { ...s.view, phase: "done", activeAgent: null }, playing: false });
  }
});

export { EMPTY_VIEW };
