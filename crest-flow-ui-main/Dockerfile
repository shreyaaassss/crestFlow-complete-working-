FROM node:22-alpine AS builder

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
FROM node:22-alpine

WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
COPY --from=builder /app/dist ./dist
# vinxi start reads vite.config.ts + tsconfig.json to locate build output
COPY --from=builder /app/vite.config.ts ./
COPY --from=builder /app/tsconfig.json ./

EXPOSE 3000

ENV PORT=3000

# TanStack Start (Vinxi) needs "vinxi start" to boot the HTTP server.
# dist/server/server.js is the SSR handler module — it doesn't self-listen.
CMD ["./node_modules/.bin/vinxi", "start"]
