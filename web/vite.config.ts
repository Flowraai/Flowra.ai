import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em dev, o painel roda em :5173 e chama a API em :8000. O proxy evita CORS local.
// Em produção, sirva a build estática e aponte VITE_API_BASE_URL para a API.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
