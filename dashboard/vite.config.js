import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy the bridge so the browser uses same-origin relative URLs (no CORS in
// dev) and WebSockets upgrade through Vite (D8). Override the target with
// VITE_BRIDGE if the bridge runs elsewhere.
const BRIDGE = process.env.VITE_BRIDGE || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/ws": { target: BRIDGE, ws: true },
      "/command": { target: BRIDGE },
      "/signals": { target: BRIDGE },
      "/healthz": { target: BRIDGE },
    },
  },
});
