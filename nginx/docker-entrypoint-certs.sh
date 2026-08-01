#!/bin/sh
# Generates a self-signed dev certificate on first start if one isn't
# already present (e.g. mounted from a volume), then hands off to nginx.
# Not for production use — real deployments terminate TLS with a
# certificate issued by a real CA / ACME.
set -e

CERT_DIR=/etc/nginx/certs

if [ ! -f "$CERT_DIR/dev.crt" ] || [ ! -f "$CERT_DIR/dev.key" ]; then
  mkdir -p "$CERT_DIR"
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -keyout "$CERT_DIR/dev.key" -out "$CERT_DIR/dev.crt" \
    -subj "/CN=localhost"
fi

exec nginx -g "daemon off;"
