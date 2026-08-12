import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  root: siteRoot,
  plugins: [react()],
  server: {
    fs: {
      allow: [resolve(siteRoot, "..")],
    },
  },
  build: {
    outDir: resolve(siteRoot, "../dist"),
    emptyOutDir: true,
  },
});
