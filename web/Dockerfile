FROM oven/bun:1.3.14-slim AS build

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .

RUN bun run build

FROM nginx:alpine

ENV API_PROXY_TARGET=http://server:8000 \
    NGINX_ENVSUBST_FILTER=^API_PROXY_TARGET$

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
