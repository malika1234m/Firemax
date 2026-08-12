# Build context is the REPO ROOT, not frontend/ — see backend/Dockerfile for
# why. Build with:
#
#   docker build -f frontend/Dockerfile .
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json .
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
# gettext supplies envsubst, used by the entrypoint to render the config.
RUN apk add --no-cache gettext

# The stock config has no /api proxy and no SPA fallback, so it is replaced.
# It is rendered at START time, not build time, because the backend upstream
# is not known until the container is deployed somewhere.
COPY frontend/nginx.conf.template /etc/nginx/nginx.conf.template
COPY frontend/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
