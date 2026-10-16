import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      // Only proxy actual image files (e.g. /products/foo.jpg) to the backend's
      // static mount. A bare prefix match here would also swallow the SPA route
      // /products/:id (e.g. on a hard navigation or page refresh), returning the
      // backend's "Not Found" JSON instead of letting React Router render the
      // product page. A leading "^" makes Vite treat the key as a RegExp.
      "^/products/.+\\.(jpg|jpeg|png|webp|gif)$": backend,
    },
  },
});
