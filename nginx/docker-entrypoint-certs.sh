#!/bin/sh
# Generates a self-signed dev certificate on first start if one isn't
# already present (e.g. mounted from a volume), then hands off to nginx.
# Not for production use — real deployments terminate TLS with a
# certificate issued by a real CA / ACME.
set -e

CERT_DIR=/etc/nginx/certs

if [ ! -f "$CERT_DIR/dev.crt" ] || [ ! -f "$CERT_DIR/dev.key" ]; then
  mkdir -p "$CERT_DIR"
  # -addext subjectAltName is required: modern Chrome/Firefox reject a
  # cert with only a CN, no SAN, as an invalid hostname match — even for
  # "localhost". Without it, background fetch()/XHR calls (the frontend's
  # API calls, as opposed to a manually-navigated page) fail the TLS
  # handshake silently and the browser reports it as a generic CORS
  # failure instead of a certificate error.
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -keyout "$CERT_DIR/dev.key" -out "$CERT_DIR/dev.crt" \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
fi

exec nginx -g "daemon off;"
