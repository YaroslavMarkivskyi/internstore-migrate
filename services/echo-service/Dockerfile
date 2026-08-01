FROM node:20-alpine
WORKDIR /app

COPY package.json pnpm-lock.yaml* ./
RUN corepack enable && corepack prepare pnpm@9 --activate && pnpm install

COPY tsconfig.json ./
COPY src ./src
RUN pnpm build

EXPOSE 4000
CMD ["node", "dist/index.js"]
