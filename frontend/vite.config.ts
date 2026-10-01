import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `--mode pages` builds the static, replay-only site for GitHub Pages, which
// is served from /ai-dev-team/. Everything else is served from the root by
// FastAPI (api.py), with the dev server proxying API calls to it.
export default defineConfig(({ mode }) => ({
  base: mode === "pages" ? "/ai-dev-team/" : "/",
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/runs": "http://127.0.0.1:8000",
      "/workspace": "http://127.0.0.1:8000",
      "/download.zip": "http://127.0.0.1:8000",
    },
  },
  build: {
    target: "es2022",
    chunkSizeWarningLimit: 1500,
  },
}));
