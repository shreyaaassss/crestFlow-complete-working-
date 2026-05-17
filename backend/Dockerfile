FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source
COPY src/ ./src/
COPY tsconfig.json ./

EXPOSE 3001

# tsx runs TypeScript directly — no compile step needed
CMD ["npx", "tsx", "src/index.ts"]
