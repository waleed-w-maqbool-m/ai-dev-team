"""Renders the no-WebGL fallback image (frontend/public/poster.jpg) from the
real stage: the Theater mid-replay, with the HUD hidden."""
import sys

from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True, args=["--ignore-gpu-blocklist", "--use-angle=d3d11"])
    page = b.new_page(viewport={"width": 1600, "height": 1000})
    page.goto("http://127.0.0.1:8000/theater?qa", wait_until="networkidle")
    page.wait_for_function("() => window.__scene && window.__scene.frames > 30")
    page.add_style_tag(content=".app,.nav,.motion-toggle,.cursor,.preloader{display:none!important}")
    page.wait_for_timeout(16000)
    page.screenshot(path=OUT, type="jpeg", quality=80)
    b.close()
