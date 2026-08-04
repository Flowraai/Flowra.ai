# syntax=docker/dockerfile:1
# --- Build da SPA ---
FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# VITE_API_BASE_URL vazio => o cliente chama /api na mesma origem; o nginx faz o proxy.
RUN npm run build

# --- Servidor estático (nginx) ---
FROM nginx:1.27-alpine AS runtime

# Host:porta do backend para o proxy /api (o entrypoint do nginx aplica o envsubst).
ENV API_UPSTREAM=api:8000

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.default.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/healthz >/dev/null 2>&1 || exit 1
