import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * El frontend se sirve bajo `/app/` (spec D-67): en la raiz, `/novels/{id}` seria
 * a la vez direccion de la aplicacion y ruta RI-03 de la API. En produccion lo
 * sirve el backend desde `dist/`; en desarrollo Vite, y todo lo que no cuelga
 * de `/app/` va al backend local. No hay mas red que esa (RI-56).
 */
const BACKEND = "http://127.0.0.1:8000";

export default defineConfig({
  base: "/app/",
  plugins: [react()],
  server: {
    proxy: {
      "^/(?!app(/|$)).*": { target: BACKEND, changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["commons/testing/setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", "dist/**"],
    restoreMocks: true,
  },
});
