FROM node:22-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source
COPY src/ ./src/
COPY tsconfig.json ./

# Orchestrator is a background polling loop — no port needed
CMD ["npx", "ts-node", "src/index.ts"]
