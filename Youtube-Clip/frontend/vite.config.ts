import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const API = process.env.VITE_API_TARGET || "http://127.0.0.1:5100";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/clips": { target: API, changeOrigin: true },
    },
  },
  build: { outDir: "dist" },
});
