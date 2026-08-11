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

# STR-145: nginx.conf's `resolver` directive was hardcoded to
# 127.0.0.11 — Docker Compose's embedded DNS server. That's not reachable
# in Kubernetes (pods get CoreDNS's ClusterIP instead, e.g. 10.96.0.10 in
# a kind cluster, but it's whatever the cluster assigns — not a fixed
# value to hardcode either). Confirmed live: every proxied request 500'd
# with "auth-backend could not be resolved (110: Operation timed out),
# resolver: 127.0.0.11:53" — nginx was trying to reach a DNS server that
# doesn't exist in-cluster. Since nginx.conf is the same file compose and
# k8s both build into internstore/nginx:local, the fix reads the real
# nameserver this container was actually handed (works out to 127.0.0.11
# under compose, CoreDNS's ClusterIP under k8s, unmodified either way) and
# patches it in before nginx starts, rather than hardcoding either value.
RESOLVER_IP="$(awk '/^nameserver/ { print $2; exit }' /etc/resolv.conf)"
if [ -n "$RESOLVER_IP" ]; then
  sed -i "s/^  resolver .*;/  resolver ${RESOLVER_IP} valid=5s;/" /etc/nginx/nginx.conf
fi

# STR-145: fixing the resolver address alone wasn't enough — with a real
# resolver reachable, every upstream still failed with "auth-backend could
# not be resolved (2: Server failure)". nginx's `resolver`-based lookups
# (used to re-resolve the `set $x_upstream "host:port"` variables above at
# request time) query literally whatever hostname is in the variable —
# unlike a normal libc resolver call (getent/curl/python), they don't
# consult /etc/resolv.conf's `search` list to expand a bare name. Docker
# Compose's embedded DNS resolves bare short names ("auth-backend")
# natively, but CoreDNS only does if the query already carries the
# cluster's search suffix, so the exact same nginx.conf 500s in-cluster on
# every route. Fix: detect the k8s-style search domain (a
# "*.svc.cluster.local" entry) in this container's own /etc/resolv.conf
# and qualify the bareword upstream hostnames with it; under compose
# there's no such entry so this is a no-op and bare names are left as-is.
SEARCH_SUFFIX="$(awk '/^search/ { for (i=2;i<=NF;i++) if ($i ~ /svc\.cluster\.local$/) { print $i; exit } }' /etc/resolv.conf)"
if [ -n "$SEARCH_SUFFIX" ]; then
  sed -i "s/\(set \$[a-zA-Z_]*_upstream \"[a-zA-Z0-9-]*\):/\1.${SEARCH_SUFFIX}:/" /etc/nginx/nginx.conf
fi

exec nginx -g "daemon off;"
