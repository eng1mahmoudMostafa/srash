import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to Django so the SPA can use same-origin
// requests (cookies/CSRF work naturally without extra CORS config).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    // Split rarely-changing vendor libraries into their own chunk so they stay
    // cached across app updates and can load in parallel with the app code.
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-dom/client"],
          router: ["react-router-dom"],
        },
      },
    },
    // Hashed asset names already enable long-lived caching; keep source maps
    // off in production to shave the payload.
    sourcemap: false,
    chunkSizeWarningLimit: 700,
  },
});