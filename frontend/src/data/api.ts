// One client for both deployments: the local FastAPI app (live runs + all
// replays) and the static GitHub Pages build (bundled replays only). Every
// call tries the API first and falls back to the static files.
import type { Replay, ReplayMeta } from "./types";

const BASE = import.meta.env.BASE_URL; // "/" locally, "/ai-dev-team/" on Pages

export interface Health {
  live: boolean;
  provider?: string;
  model?: string;
  sandbox?: string;
}

export interface BenchmarkConfig {
  name: string;
  model: string;
  testing_agent: string;
  runs: number;
  solved: number;
  check_rate: number;
  claimed: number;
  false_done: number;
  llm_calls: number;
  tokens: number;
  seconds: number;
}

export interface Benchmark {
  generated_at: string | null;
  task_count: number;
  case_count: number;
  configs: BenchmarkConfig[];
  per_task: { task: string; difficulty: string; results: Record<string, string> }[];
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  const type = res.headers.get("content-type") ?? "";
  if (!type.includes("json")) throw new Error(`not JSON: ${url}`);
  return res.json() as Promise<T>;
}

async function withFallback<T>(apiPath: string, staticPath: string): Promise<T> {
  try {
    return await getJson<T>(`${BASE}api/${apiPath}`);
  } catch {
    return getJson<T>(`${BASE}${staticPath}`);
  }
}

let healthPromise: Promise<Health> | null = null;

export const api = {
  health(): Promise<Health> {
    healthPromise ??= getJson<Health>(`${BASE}api/health`).catch(() => ({ live: false }));
    return healthPromise;
  },
  replays: () => withFallback<ReplayMeta[]>("replays", "replays/index.json"),
  replay: (id: string) => withFallback<Replay>(`replays/${encodeURIComponent(id)}`, `replays/${encodeURIComponent(id)}.json`),
  benchmark: () => withFallback<Benchmark>("benchmark", "benchmark.json"),
  liveRunUrl: (request: string) => `${BASE}runs?request=${encodeURIComponent(request)}`,
  workspaceFileUrl: (path: string) => `${BASE}workspace/${path.split("/").map(encodeURIComponent).join("/")}`,
  zipUrl: (files: string[], name: string) =>
    `${BASE}download.zip?${files.map((f) => `files=${encodeURIComponent(f)}`).join("&")}&name=${encodeURIComponent(name)}`,
};
