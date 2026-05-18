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
# Custom HTTP server that wraps the Fetch API handler from dist/server/server.js
COPY --from=builder /app/server.mjs ./

EXPOSE 3000

ENV PORT=3000

# server.mjs: wraps dist/server/server.js (Fetch handler) in a Node.js HTTP server
CMD ["node", "server.mjs"]
