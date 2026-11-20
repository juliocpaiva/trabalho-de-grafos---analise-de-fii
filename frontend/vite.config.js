import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// VITE_BASE = caminho do site publicado (ex.: /nome-do-repositorio/ no GitHub Pages).
export default defineConfig({
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
