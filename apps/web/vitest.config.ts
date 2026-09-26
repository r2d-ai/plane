import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./core", import.meta.url)),
      "next/navigation": fileURLToPath(new URL("./tests/mocks/next-navigation.ts", import.meta.url)),
      "next/link": fileURLToPath(new URL("./tests/mocks/next-link.tsx", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    globals: true,
    setupFiles: ["./tests/vitest.setup.ts"],
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
  },
});
