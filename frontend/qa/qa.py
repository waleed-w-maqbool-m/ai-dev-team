"""Phase 3 self-verification loop for the web console.

Drives headless Edge through every check in the brief and writes artefacts +
report.json to OUT_DIR. Expects `python api.py` serving the built frontend.

Usage: python frontend/qa/qa.py OUT_DIR
"""
import json
import os
import statistics
import sys
import time

from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
sys.stdout.reconfigure(encoding="utf-8")
BASE = os.environ.get("QA_BASE", "http://127.0.0.1:8000")
GPU_ARGS = ["--ignore-gpu-blocklist", "--enable-gpu-rasterization", "--use-angle=d3d11"]
AXE = os.path.join(os.path.dirname(__file__), "..", "node_modules", "axe-core", "axe.min.js")
VIEWPORTS = {"mobile": (390, 844), "tablet": (768, 1024), "desktop": (1440, 900)}
IGNORED_CONSOLE = ("THREE.Clock",)  # deprecation warning from inside @react-three/fiber

os.makedirs(OUT, exist_ok=True)
report: dict = {"checks": {}, "metrics": {}}


def check(name, ok, detail=None):
    report["checks"][name] = {"ok": bool(ok), "detail": detail}
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail is not None else ""), flush=True)


def wait_ready(page, timeout=30000):
    page.wait_for_function("() => window.__scene && window.__scene.frames > 30", timeout=timeout)
    page.wait_for_timeout(2600)  # preloader exit + first reveals


def nonblank(page) -> float:
    """Share of sampled canvas pixels that differ from the background colour."""
    return page.evaluate("""() => {
      const src = document.querySelector('.stage canvas');
      if (!src) return 0;
      const c = document.createElement('canvas'); c.width = 96; c.height = 60;
      const g = c.getContext('2d'); g.drawImage(src, 0, 0, 96, 60);
      const d = g.getImageData(0, 0, 96, 60).data; let n = 0;
      for (let i = 0; i < d.length; i += 4) if (Math.abs(d[i]-7)+Math.abs(d[i+1]-8)+Math.abs(d[i+2]-10) > 24) n++;
      return n / (96 * 60);
    }""")


FPS_JS = """(ms) => new Promise(res => {
  const times = []; let last = performance.now(); const end = last + ms;
  function f(t) { times.push(t - last); last = t; if (t < end) requestAnimationFrame(f); else {
    times.shift(); const fps = times.map(d => 1000 / d).sort((a, b) => a - b);
    res({ avg: 1000 / (times.reduce((a, b) => a + b, 0) / times.length), p5: fps[Math.floor(fps.length * 0.05)], frames: times.length });
  } }
  requestAnimationFrame(f);
})"""


def scroll_steps(page, tag, steps=11, delay=1300):
    total = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    shots = []
    for i in range(steps):
        frac = i / (steps - 1)
        page.evaluate(f"window.scrollTo(0, {int(total * frac)})")
        page.wait_for_timeout(delay)
        path = f"{OUT}/{tag}-scroll-{i * 10:03d}.png"
        page.screenshot(path=path)
        shots.append(path)
    return shots


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True, args=GPU_ARGS)

    # ---------- A. correctness + B. choreography (desktop, with video) ----------
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=OUT, record_video_size={"width": 1440, "height": 900})
    page = ctx.new_page()
    console, failed = [], []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") and not any(s in m.text for s in IGNORED_CONSOLE) else None)
    page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed.append(f"{r.url} {r.failure}"))
    page.on("response", lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    page.goto(f"{BASE}/?qa", wait_until="networkidle")
    wait_ready(page)
    report["metrics"]["renderer"] = page.evaluate("window.__scene.renderer")
    check("A3 five stations registered", page.evaluate("window.__scene.stations.length") == 5)
    check("E fonts loaded", page.evaluate("document.fonts.check('40px \"Instrument Serif\"') && document.fonts.check('16px \"Geist Variable\"')"))

    blank_by_section = {}
    total = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    for i in range(41):  # slow scripted scroll for the video, sampling pixels on the way
        page.evaluate(f"window.scrollTo(0, {int(total * i / 40)})")
        page.wait_for_timeout(650)
        t = page.evaluate("window.__scene.storyTime")
        blank_by_section.setdefault(int(min(t, 4.99)), []).append(nonblank(page))
    report["metrics"]["nonblank_by_section"] = {k: round(min(v), 3) for k, v in blank_by_section.items()}
    # A blank canvas scores ~0; the Proof section is dimmed on purpose, so the
    # bar is "never blank", not "always bright".
    check("A2 canvas never blank in any section", all(min(v) > 0.01 for v in blank_by_section.values()), report["metrics"]["nonblank_by_section"])

    # C. interactivity on the hero: cursor tilt + hover CAD frame
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(1500)
    before = page.evaluate("window.__scene.rig")
    for x, y in [(200, 200), (700, 450), (1300, 300), (1350, 750)]:
        page.mouse.move(x, y, steps=12)
        page.wait_for_timeout(250)
    page.wait_for_timeout(900)
    after = page.evaluate("window.__scene.rig")
    page.screenshot(path=f"{OUT}/C-tilt-after.png")
    check("C1 stage tilts toward the cursor", abs(after[1] - before[1]) > 0.02, {"before": before, "after": after})
    page.mouse.move(720, 450)
    page.wait_for_timeout(2400)
    breathe1 = page.evaluate("window.__scene.rig")
    page.wait_for_timeout(1500)
    breathe2 = page.evaluate("window.__scene.rig")
    check("C1b idle breathing when the cursor is still", abs(breathe1[1] - breathe2[1]) > 0.0005, {"t1": breathe1, "t2": breathe2})

    # Hover each station on the steady hero shot.
    hits = {}
    for agent in ["pm", "swe", "testing", "qa", "docs"]:
        x, y = page.evaluate(f"window.__scene.stationScreen('{agent}')")
        page.mouse.move(x, y, steps=6)
        page.wait_for_timeout(700)
        hits[agent] = page.evaluate("window.__scene.hovered")
        if agent == "qa":
            page.screenshot(path=f"{OUT}/C-hover-qa.png")
    check("C2 hovering each station frames it (CAD box)", all(hits[a] == a for a in hits), hits)

    page.goto(f"{BASE}/theater?qa", wait_until="networkidle")
    wait_ready(page)

    # Replay controls: hold to fast-forward, seek.
    page.wait_for_timeout(1500)
    hold = page.locator(".tl-btn--hold")
    c0 = int(page.locator(".timeline__count").inner_text().split("/")[0])
    hold.hover()
    page.mouse.down()
    page.wait_for_timeout(2600)
    speed_active = page.locator(".tl-btn--hold[data-active]").count() == 1
    page.mouse.up()
    c1 = int(page.locator(".timeline__count").inner_text().split("/")[0])
    check("C3 hold-to-fast-forward advances the replay", speed_active and c1 > c0, {"before": c0, "after": c1})
    page.locator(".tick").nth(2).click()
    page.wait_for_timeout(600)
    check("C4 clicking a timeline tick selects that event", page.locator(".tick[data-selected]").count() == 1 or c1 < 3)
    ctx.close()
    video = [f for f in os.listdir(OUT) if f.endswith(".webm")]
    if video:
        os.replace(os.path.join(OUT, video[0]), os.path.join(OUT, "B-scroll-desktop.webm"))
    check("A1 zero console errors / warnings", not console, console[:10])
    check("A1 zero failed requests", not failed, failed[:10])

    # ---------- B. scroll steps at 3 viewports + E. overflow ----------
    for name, (w, h) in VIEWPORTS.items():
        ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=name == "mobile", is_mobile=name == "mobile")
        page = ctx.new_page()
        page.goto(f"{BASE}/?qa", wait_until="networkidle")
        wait_ready(page)
        scroll_steps(page, name)
        overflow = {}
        for route in ["", "theater", "library", "benchmark"]:
            page.goto(f"{BASE}/{route}?qa", wait_until="networkidle")
            page.wait_for_timeout(3500 if route else 2500)
            overflow[route or "story"] = page.evaluate("document.documentElement.scrollWidth - innerWidth")
            page.screenshot(path=f"{OUT}/{name}-{route or 'story'}.png")
        check(f"E no horizontal overflow ({name})", all(v <= 0 for v in overflow.values()), overflow)
        ctx.close()

    # ---------- C. keyboard-only pass ----------
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(f"{BASE}/theater?qa", wait_until="networkidle")
    wait_ready(page)
    seen, no_outline = [], []
    for i in range(22):
        page.keyboard.press("Tab")
        info = page.evaluate("""() => { const e = document.activeElement; const s = getComputedStyle(e);
          return { tag: e.tagName, text: (e.getAttribute('aria-label') || e.textContent || e.id || '').trim().slice(0, 40),
                   outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 || e.matches('input,select') }; }""")
        seen.append(f"{info['tag']}:{info['text']}")
        if not info["outline"] and info["tag"] != "BODY":  # focus wrapping past the last control
            no_outline.append(info["text"])
        if i == 6:
            page.screenshot(path=f"{OUT}/C-keyboard-focus.png")
    report["metrics"]["tab_order"] = seen
    run_enabled = not page.locator(".topbar button[type=submit]").is_disabled()
    ticks_in_order = sum(1 for s in seen if s.startswith("BUTTON:") and (": " in s and s.split(":")[1].strip().isdigit() or "Event " in s))
    reachable = (
        any(s.startswith("INPUT:") for s in seen)
        and (any("Run live" in s for s in seen) or not run_enabled)  # a disabled button is correctly skipped
        and any("All runs" in s for s in seen)  # recordings are picked on the Runs page
        and any("Hold" in s for s in seen)
        and ticks_in_order == 1
    )
    check("C5 keyboard reaches request, run, runs link and timeline (one stop)", reachable, {"run_enabled": run_enabled, "tick_stops": ticks_in_order, "order": seen[:16]})
    # Arrow keys move along the timeline.
    page.locator(".tick[tabindex='0']").focus()
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    check("C5b arrow keys move between timeline events", page.evaluate("document.activeElement.getAttribute('aria-label') || ''").startswith("2:"))
    check("C5 focus is visible on every stop", not no_outline, no_outline)
    ctx.close()

    # ---------- D. performance ----------
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(f"{BASE}/?qa", wait_until="networkidle")
    wait_ready(page)
    page.evaluate("""() => { let y = 0; const H = document.documentElement.scrollHeight;
      window.__scrollTimer = setInterval(() => { y = (y + 18) % H; window.scrollTo(0, y); }, 16); }""")
    fps_story = page.evaluate(FPS_JS, 8000)
    page.evaluate("clearInterval(window.__scrollTimer)")
    gl0 = page.evaluate("window.__scene.gl")
    page.goto(f"{BASE}/theater?qa", wait_until="networkidle")
    wait_ready(page)
    for i in range(10):
        page.mouse.move(200 + i * 100, 300 + (i % 3) * 120, steps=8)
    fps_theater = page.evaluate(FPS_JS, 8000)
    report["metrics"]["fps_desktop_story"] = fps_story
    report["metrics"]["fps_desktop_theater"] = fps_theater
    report["metrics"]["tier_after_desktop"] = page.evaluate("window.__scene.tier")
    report["metrics"]["dpr_after_desktop"] = page.evaluate("window.__scene.dpr")
    check("D1 desktop fps >= 50 on this laptop (story scroll)", fps_story["avg"] >= 50, fps_story)
    check("D1 desktop fps >= 50 on this laptop (theater)", fps_theater["avg"] >= 50, fps_theater)
    # Memory: walk every route twice; GPU resources must not keep growing.
    counts = []
    for _ in range(2):
        for route in ["library", "", "theater", "benchmark", "theater"]:
            page.goto(f"{BASE}/{route}?qa", wait_until="networkidle")
            page.wait_for_timeout(1800)
        counts.append(page.evaluate("window.__scene.gl"))
    report["metrics"]["gl_memory"] = {"start": gl0, "pass1": counts[0], "pass2": counts[1]}
    check("D3 GPU resources stable across route changes", counts[1]["geometries"] <= counts[0]["geometries"] + 2 and counts[1]["textures"] <= counts[0]["textures"] + 2, report["metrics"]["gl_memory"])
    ctx.close()

    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    page.goto(f"{BASE}/theater?qa", wait_until="networkidle")
    wait_ready(page, timeout=90000)
    fps_mobile = page.evaluate(FPS_JS, 8000)
    report["metrics"]["fps_mobile_cpu4x"] = fps_mobile
    check("D1 mobile fps >= 30 with 4x CPU throttling", fps_mobile["avg"] >= 30, fps_mobile)
    ctx.close()

    # ---------- E. accessibility ----------
    # bypass_csp: the deployed CSP (script-src 'self') rightly blocks injecting axe.
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, bypass_csp=True)
    page = ctx.new_page()
    axe_results = {}
    for route in ["", "theater", "library", "benchmark"]:
        page.goto(f"{BASE}/{route}?qa", wait_until="networkidle")
        wait_ready(page)
        page.add_script_tag(path=AXE)
        res = page.evaluate("() => axe.run(document, { resultTypes: ['violations'] })")
        bad = [{"id": v["id"], "impact": v["impact"], "nodes": len(v["nodes"]), "help": v["help"]} for v in res["violations"] if v["impact"] in ("serious", "critical")]
        axe_results[route or "story"] = bad
    report["metrics"]["axe"] = axe_results
    check("E1 axe: zero serious/critical issues", all(not v for v in axe_results.values()), axe_results)
    ctx.close()

    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(f"{BASE}/?qa", wait_until="networkidle")
    wait_ready(page)
    scroll_steps(page, "reduced", steps=6, delay=900)
    words = page.evaluate("document.querySelector('main').innerText.split(/\\s+/).length")
    check("E2 reduced motion: content complete", page.evaluate("document.documentElement.dataset.motion") == "reduced" and words > 150, {"words": words})
    ctx.close()
    browser.close()

    nogl = p.chromium.launch(channel="msedge", headless=True, args=["--disable-webgl", "--disable-3d-apis"])
    page = nogl.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_timeout(4000)
    page.screenshot(path=f"{OUT}/E-nowebgl-story.png")
    poster = page.locator(".stage-poster").count() == 1
    page.goto(f"{BASE}/theater", wait_until="networkidle")
    page.wait_for_timeout(6000)
    page.screenshot(path=f"{OUT}/E-nowebgl-theater.png")
    events = page.locator(".tick[data-reached]").count()
    check("E3 WebGL disabled: poster fallback + replay still plays", poster and events > 0, {"poster": poster, "events_played": events})
    nogl.close()

with open(f"{OUT}/report.json", "w") as f:
    json.dump(report, f, indent=1)
failed_checks = [k for k, v in report["checks"].items() if not v["ok"]]
print(f"\n{len(report['checks']) - len(failed_checks)}/{len(report['checks'])} checks passed")
for k in failed_checks:
    print("  FAILED:", k)
