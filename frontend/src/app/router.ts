// A four-route router is small enough not to need a library. Paths are
// relative to Vite's BASE_URL so the same build works at "/" (FastAPI) and
// "/ai-dev-team/" (GitHub Pages, which falls back to 404.html → index.html).
import { useSyncExternalStore } from "react";

export type Route = "story" | "theater" | "library" | "benchmark";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
const PATHS: Record<Route, string> = { story: "/", theater: "/theater", library: "/library", benchmark: "/benchmark" };

export function routeFromLocation(): Route {
  const path = window.location.pathname.slice(BASE.length).replace(/\/$/, "") || "/";
  return (Object.keys(PATHS) as Route[]).find((r) => PATHS[r] === path) ?? "story";
}

export function hrefFor(route: Route, query = ""): string {
  return `${BASE}${PATHS[route]}${query}`;
}

const listeners = new Set<() => void>();
window.addEventListener("popstate", () => listeners.forEach((l) => l()));

export function navigate(route: Route, query = "") {
  const go = () => {
    window.history.pushState(null, "", hrefFor(route, query));
    listeners.forEach((l) => l());
    window.scrollTo(0, 0);
  };
  const doc = document as Document & { startViewTransition?: (cb: () => void) => unknown };
  const reduce = document.documentElement.dataset.motion === "reduced";
  if (doc.startViewTransition && !reduce) doc.startViewTransition(go);
  else go();
}

export function useRoute(): Route {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    routeFromLocation,
  );
}

export function queryParam(name: string): string | null {
  return new URLSearchParams(window.location.search).get(name);
}
