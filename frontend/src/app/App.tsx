import { useEffect, useState, type ComponentType } from "react";

import { BenchmarkPage } from "../pages/BenchmarkPage";
import { LibraryPage } from "../pages/LibraryPage";
import { StoryPage } from "../story/StoryPage";
import { GITHUB_URL } from "../story/content";
import { TheaterPage } from "../theater/TheaterPage";
import { Cursor } from "../ui/Cursor";
import { MotionToggle } from "../ui/MotionToggle";
import { Preloader } from "./Preloader";
import { hrefFor, navigate, useRoute, type Route } from "./router";
import { sceneSignals, useUi } from "./uiStore";

function webglAvailable(): boolean {
  if (new URLSearchParams(window.location.search).has("nowebgl")) return false;
  try {
    const c = document.createElement("canvas");
    return Boolean(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

const LINKS: { route: Route; label: string; secondary?: boolean }[] = [
  { route: "story", label: "Story" },
  { route: "theater", label: "Theater" },
  { route: "library", label: "Runs", secondary: true },
  { route: "benchmark", label: "Benchmark", secondary: true },
];

function Nav({ route }: { route: Route }) {
  return (
    <header className="nav">
      <a
        className="brand"
        href={hrefFor("story")}
        onClick={(e) => {
          e.preventDefault();
          navigate("story");
        }}
      >
        <svg className="brand__mark" viewBox="0 0 18 18" aria-hidden="true">
          <circle cx="3" cy="9" r="2" fill="#FF5B1F" />
          <circle cx="15" cy="9" r="2" fill="#ECEAE4" />
          <path d="M5 9 C 8 3, 10 15, 13 9" stroke="#FFB27A" strokeWidth="1.2" fill="none" />
        </svg>
        <span className="brand__name">AI Dev Team</span>
      </a>
      <nav className="nav__links" aria-label="Primary">
        {LINKS.map((l) => (
          <a
            key={l.route}
            className={`nav__link ${l.secondary ? "nav__link--secondary" : ""}`}
            href={hrefFor(l.route)}
            aria-current={route === l.route ? "page" : undefined}
            onClick={(e) => {
              e.preventDefault();
              navigate(l.route);
            }}
          >
            {l.label}
          </a>
        ))}
        <a className="nav__link" href={GITHUB_URL} target="_blank" rel="noreferrer">
          GitHub ↗
        </a>
      </nav>
    </header>
  );
}

export function App() {
  const route = useRoute();
  const sceneReady = useUi((s) => s.sceneReady);
  const setSceneReady = useUi((s) => s.setSceneReady);
  const [webgl] = useState(webglAvailable);
  const [Stage, setStage] = useState<ComponentType<{ paused: boolean }> | null>(null);
  const [fontsReady, setFontsReady] = useState(false);

  useEffect(() => {
    sceneSignals.mode = route === "story" ? "story" : route === "theater" ? "theater" : "page";
    document.title =
      route === "theater" ? "Theater · AI Dev Team" : route === "library" ? "Runs · AI Dev Team" : route === "benchmark" ? "Benchmark · AI Dev Team" : "AI Dev Team";
  }, [route]);

  useEffect(() => {
    document.fonts.ready.then(() => setFontsReady(true));
    if (webgl) {
      // Fetch the 3D bundle once the first paint is done, so parsing it
      // doesn't compete with the page's own startup work.
      const load = () => import("../scene/Stage").then((m) => setStage(() => m.default));
      if ("requestIdleCallback" in window) window.requestIdleCallback(load, { timeout: 800 });
      else setTimeout(load, 200);
    }
  }, [webgl]);

  useEffect(() => {
    if (!webgl && fontsReady) setSceneReady();
  }, [webgl, fontsReady, setSceneReady]);

  const progress = sceneReady ? 100 : Stage ? 80 : fontsReady ? 40 : 12;

  return (
    <>
      <a className="skip-link" href="#main">Skip to content</a>
      {webgl ? Stage && <Stage paused={false} /> : <div className="stage-poster" aria-hidden="true" />}
      <Nav route={route} />
      <div className="app">
        {route === "story" && <StoryPage />}
        {route === "theater" && <TheaterPage />}
        {route === "library" && <LibraryPage />}
        {route === "benchmark" && <BenchmarkPage />}
      </div>
      <MotionToggle />
      <Cursor />
      <Preloader progress={progress} />
    </>
  );
}
