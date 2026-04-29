# Multi-stage build for the React/Vite frontend.
#
# Dev: docker-compose.dev.yml mounts ./frontend over /app and runs `pnpm dev`,
# so only the deps stage is exercised at runtime.
# Prod: build stage produces /app/dist, served by nginx via the runtime stage.

ARG NODE_VERSION=20-alpine

# ---- deps ----------------------------------------------------------------
FROM node:${NODE_VERSION} AS deps
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.33.0 --activate
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

# ---- build ---------------------------------------------------------------
FROM node:${NODE_VERSION} AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.33.0 --activate
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# ---- runtime (prod) -------------------------------------------------------
FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# ---- dev (default target) -------------------------------------------------
FROM node:${NODE_VERSION} AS dev
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.33.0 --activate
ENV HOST=0.0.0.0
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
