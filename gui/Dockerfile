# The API base is baked in at build time - Vite inlines import.meta.env into
# the bundle, so this is a build argument and not a runtime environment
# variable. The default is the host's port mapping, because the browser runs
# on the host and cannot resolve compose service names.
FROM node:22-alpine AS build

ARG VITE_API_BASE=http://localhost:8200
ENV VITE_API_BASE=${VITE_API_BASE}

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
