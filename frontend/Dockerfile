# syntax=docker/dockerfile:1

FROM node:20-alpine AS build
WORKDIR /app

# package-lock.json is written by npm 11; npm 10 (bundled with Node 20) rejects it.
RUN npm install -g npm@11.6.2 --no-audit --no-fund
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD wget -q --spider http://127.0.0.1/ || exit 1
