#!/bin/sh
# Docker entrypoint: run DB migrations, optionally start the embedded nginx
# (START_NGINX=true for the all-in-one Alpine image), then exec the given
# command (gunicorn by default).
set -eu

log() {
  printf '[entrypoint] %s\n' "$*" >&2
}

run_migrations() {
  if [ "${SKIP_MIGRATIONS:-false}" = "true" ]; then
    log "SKIP_MIGRATIONS=true; skipping flask db upgrade"
    return
  fi

  log "Applying database migrations (flask db upgrade)..."
  flask db upgrade
  log "Migrations complete."
}

# Make sure the runtime dirs exist and are writable by the unprivileged user.
mkdir -p /app/instance /app/uploads /tmp/nginx

if [ "${START_NGINX:-false}" = "true" ]; then
  log "Starting embedded nginx..."
  nginx
fi

run_migrations

log "Executing: $*"
exec "$@"
