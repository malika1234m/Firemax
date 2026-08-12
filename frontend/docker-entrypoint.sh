#!/bin/sh
# Renders nginx.conf.template, then starts nginx.
#
# envsubst is given an EXPLICIT variable list. Without it, envsubst would also
# expand nginx's own runtime variables ($host, $remote_addr, $http_upgrade, …)
# into empty strings and produce a config that is silently wrong.
set -eu

: "${PORT:=80}"
: "${BACKEND_ORIGIN:=http://backend:8000}"

# Host header for the upstream: derived from BACKEND_ORIGIN unless overridden.
if [ -z "${BACKEND_HOST:-}" ]; then
  BACKEND_HOST=$(printf '%s' "$BACKEND_ORIGIN" | sed -e 's#^[a-zA-Z][a-zA-Z0-9+.-]*://##' -e 's#/.*$##')
fi

export PORT BACKEND_ORIGIN BACKEND_HOST

echo "[entrypoint] listen=${PORT} upstream=${BACKEND_ORIGIN} host=${BACKEND_HOST}"

envsubst '${PORT} ${BACKEND_ORIGIN} ${BACKEND_HOST}' \
  < /etc/nginx/nginx.conf.template \
  > /etc/nginx/conf.d/default.conf

# Fail fast and loudly on a bad config rather than crash-looping opaquely.
nginx -t

exec nginx -g 'daemon off;'
