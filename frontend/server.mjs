/**
 * Production HTTP server for CrestFlow frontend (TanStack Start SSR).
 *
 * TanStack Start builds to dist/server/server.js which exports a Fetch API handler.
 * This file wraps it in a Node.js HTTP server so it can run as a container.
 *
 * Static assets from dist/client/ are served directly with long-lived cache headers.
 * All other requests are passed to the SSR handler.
 */

import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { join, extname } from "node:path";

const PORT = parseInt(process.env.PORT || "3000", 10);
const STATIC_DIR = join(process.cwd(), "dist/client");

// Import the compiled SSR handler
const mod = await import("./dist/server/server.js");
const handler = mod.default;

const MIME = {
  ".js":    "text/javascript; charset=utf-8",
  ".mjs":   "text/javascript; charset=utf-8",
  ".css":   "text/css; charset=utf-8",
  ".html":  "text/html; charset=utf-8",
  ".json":  "application/json",
  ".png":   "image/png",
  ".jpg":   "image/jpeg",
  ".jpeg":  "image/jpeg",
  ".svg":   "image/svg+xml",
  ".ico":   "image/x-icon",
  ".woff":  "font/woff",
  ".woff2": "font/woff2",
  ".ttf":   "font/ttf",
  ".webp":  "image/webp",
};

async function tryStatic(pathname, res) {
  const filePath = join(STATIC_DIR, pathname);
  try {
    const info = await stat(filePath);
    if (!info.isFile()) return false;
    const content = await readFile(filePath);
    const mime = MIME[extname(filePath)] || "application/octet-stream";
    res.writeHead(200, {
      "Content-Type": mime,
      "Cache-Control": "public, max-age=31536000, immutable",
    });
    res.end(content);
    return true;
  } catch {
    return false;
  }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);

  // 1. Try to serve from dist/client/ (hashed assets, etc.)
  if (await tryStatic(url.pathname, res)) return;

  // 2. SSR — convert Node IncomingMessage → Fetch Request → Fetch Response → Node res
  const headers = new Headers();
  for (const [k, v] of Object.entries(req.headers)) {
    if (v != null) headers.set(k, Array.isArray(v) ? v.join(", ") : v);
  }

  let body = undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    body = await new Promise((resolve) => {
      const chunks = [];
      req.on("data", (c) => chunks.push(c));
      req.on("end", () => resolve(Buffer.concat(chunks)));
    });
  }

  try {
    const request = new Request(url.toString(), { method: req.method, headers, body });
    const response = await handler.fetch(request, {}, {});

    res.statusCode = response.status;
    for (const [k, v] of response.headers.entries()) {
      res.setHeader(k, v);
    }

    if (response.body) {
      const reader = response.body.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        res.write(value);
      }
    }
    res.end();
  } catch (err) {
    console.error("[SSR Error]", err);
    res.writeHead(500, { "Content-Type": "text/plain" });
    res.end("Internal Server Error");
  }
});

server.listen(PORT, () => {
  console.log(`CrestFlow frontend listening on :${PORT}`);
});
