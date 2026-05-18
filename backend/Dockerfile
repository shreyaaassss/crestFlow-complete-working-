FROM node:22-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source
COPY src/ ./src/
COPY tsconfig.json ./

# Port must match BACKEND_PORT env var (default 3002)
EXPOSE 3002

# tsx runs TypeScript directly — no compile step needed
CMD ["npx", "tsx", "src/index.ts"]
