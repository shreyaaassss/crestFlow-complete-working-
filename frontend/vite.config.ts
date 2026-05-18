// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - tanstackStart, viteReact, tailwindcss, tsConfigPaths, cloudflare (build-only),
//     componentTagger (dev-only), VITE_* env injection, @ path alias, React/TanStack dedupe,
//     error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... } }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";
import { nodePolyfills } from "vite-plugin-node-polyfills";

// Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
export default defineConfig({
  // Disable Cloudflare plugin so the build targets Node.js (AWS ECS compatible).
  cloudflare: false,
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    // @perawallet/connect uses @walletconnect/client v1 which relies on Node.js globals
    // (global, Buffer, process) that don't exist in the browser. Polyfill them.
    plugins: [
      nodePolyfills({
        globals: { global: true, Buffer: true, process: true },
        protocolImports: true,
      }),
    ],
  },
});
