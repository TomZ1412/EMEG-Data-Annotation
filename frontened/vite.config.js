import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    open: true,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:10000",
        changeOrigin: true
      },
      "/serve_image": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:10000",
        changeOrigin: true
      }
    }
  },
  optimizeDeps: {
    include: ["plotly.js-dist-min"] // ✅ 让Vite预构建Plotly
  }
});
