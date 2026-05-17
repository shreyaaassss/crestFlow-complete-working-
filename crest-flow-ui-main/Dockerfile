FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# VITE_* vars are baked in at build time — passed as build args
ARG VITE_API_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_ADMIN_EMAIL

ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_SUPABASE_URL=${VITE_SUPABASE_URL}
ENV VITE_SUPABASE_ANON_KEY=${VITE_SUPABASE_ANON_KEY}
ENV VITE_ADMIN_EMAIL=${VITE_ADMIN_EMAIL}

RUN npm run build

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM node:20-alpine

WORKDIR /app

# Copy the full build output and node_modules (Vinxi embeds its own server)
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
COPY --from=builder /app/.vinxi ./.vinxi
# Also copy dist/ in case the preset outputs there instead of .vinxi/
COPY --from=builder /app/dist ./dist

EXPOSE 3000

ENV PORT=3000

# TanStack Start (Vinxi) Node.js build output.
# Vinxi outputs to .vinxi/build/server/index.mjs by default when cloudflare=false.
# Falls back to dist/server/index.js if not found.
CMD ["sh", "-c", "\
  if [ -f .vinxi/build/server/index.mjs ]; then \
    exec node .vinxi/build/server/index.mjs; \
  elif [ -f dist/server/index.js ]; then \
    exec node dist/server/index.js; \
  else \
    echo 'Server entry not found. Build output:'; \
    ls -la .vinxi/build/server/ 2>/dev/null || echo '  (no .vinxi/build/server/)'; \
    ls -la dist/server/ 2>/dev/null || echo '  (no dist/server/)'; \
    exit 1; \
  fi"]
