import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, the Vite dev server runs on port 5173 and proxies API
// requests to the FastAPI backend on port 8000. In production, the frontend
// is built and served directly by FastAPI on port 8000, so no proxy is needed.
const API_TARGET = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/health": { target: API_TARGET, changeOrigin: true },
      "/ceremonies": { target: API_TARGET, changeOrigin: true },
      "/participants": { target: API_TARGET, changeOrigin: true },
      "/attempts": { target: API_TARGET, changeOrigin: true },
      "/contributions": { target: API_TARGET, changeOrigin: true },
    },
  },
});
