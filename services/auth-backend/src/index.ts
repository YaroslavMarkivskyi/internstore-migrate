import Fastify from "fastify";
import cookie from "@fastify/cookie";
import { loadConfig } from "./config.js";
import { createExternalTokenVerifier } from "./auth/externalToken.js";
import { createInternalTokenIssuer } from "./auth/internalToken.js";
import { createRevocationChecker } from "./auth/revocation.js";
import { createGuestSessionStore, GUEST_SESSION_TTL_SECONDS } from "./auth/guestSession.js";

const config = loadConfig();
const verifyExternalToken = createExternalTokenVerifier(config.keycloakIssuer, config.keycloakJwksUri);
const mintInternalToken = createInternalTokenIssuer(config.internalTokenSecret, config.internalTokenTtlSeconds);
const isRevoked = createRevocationChecker(config.redisUrl);
const guestSessionStore = createGuestSessionStore(config.redisUrl);

// Cart/checkout, chat, and chat attachment uploads are reachable without a
// Keycloak login — these are the only paths /auth/verify grants a
// role=guest fallback token for. Order history (/api/orders/orders) is
// deliberately NOT included: a guest can check out but must register/log
// in to see past orders. /ws/room and /api/chat/rooms are shared by both
// guest-usable paths (WS connect, attachment upload) and admin-only ones
// (GET /rooms, DELETE /rooms/:id) — that's fine, chat's own
// require_admin dependency rejects a guest token on the admin-only routes;
// this allowlist only controls whether auth-backend issues a guest
// fallback token at all, not what that token is allowed to do downstream.
const GUEST_ALLOWED_PATH_PREFIXES = [
  "/api/orders/cart",
  "/api/orders/checkout",
  "/ws/room",
  "/api/chat/rooms",
];
const GUEST_COOKIE_NAME = "is_guest_id";

function isGuestAllowedPath(originalUri: string): boolean {
  const path = originalUri.split("?")[0] ?? originalUri;
  return GUEST_ALLOWED_PATH_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}

const app = Fastify({ logger: true });
await app.register(cookie);

app.get("/health", async () => ({ status: "ok" }));

// Demonstrates AUTH-03: validate the Keycloak-issued external token via
// JWKS (no per-request call to Keycloak), then mint a short-lived internal
// token that downstream services trust without contacting Keycloak or the
// Gateway.
app.get("/me", async (request, reply) => {
  const authHeader = request.headers.authorization;
  if (!authHeader?.startsWith("Bearer ")) {
    return reply.code(401).send({ error: "Missing bearer token" });
  }

  const externalToken = authHeader.slice("Bearer ".length);

  try {
    const claims = await verifyExternalToken(externalToken);
    const internalToken = await mintInternalToken(claims);
    return { sub: claims.sub, email: claims.email, role: claims.role, internalToken };
  } catch (err) {
    request.log.warn({ err }, "external token verification failed");
    return reply.code(401).send({ error: "Invalid token" });
  }
});

// nginx `auth_request` target: on-prem entry point. Same validation logic
// an AWS ALB Lambda@Edge/authorizer would call — this handler has no
// nginx-specific code, only HTTP status + headers, so it's reusable as-is
// under either topology (see services/auth-backend/README.md).
app.get("/auth/verify", async (request, reply) => {
  const authHeader = request.headers.authorization;
  if (!authHeader?.startsWith("Bearer ")) {
    // No external token presented. Only fall back to a guest identity on
    // the paths Orders explicitly allows guests on (X-Original-URI is set
    // by nginx's auth_request subrequest — see nginx.conf) — every other
    // route still 401s exactly as before.
    const originalUri = request.headers["x-original-uri"];
    if (typeof originalUri !== "string" || !isGuestAllowedPath(originalUri)) {
      return reply.code(401).send();
    }

    try {
      const existingGuestId = request.cookies[GUEST_COOKIE_NAME];
      let guestId: string;
      if (existingGuestId && (await guestSessionStore.lookup(existingGuestId))) {
        guestId = existingGuestId;
      } else {
        guestId = await guestSessionStore.create();
        reply.setCookie(GUEST_COOKIE_NAME, guestId, {
          path: "/",
          maxAge: GUEST_SESSION_TTL_SECONDS,
          httpOnly: true,
          secure: true,
          sameSite: "lax",
        });
      }
      const internalToken = await mintInternalToken({ sub: guestId, role: "guest" });
      reply.header("X-User-Id", guestId);
      reply.header("X-User-Role", "guest");
      reply.header("X-Internal-Token", internalToken);
      return reply.code(200).send();
    } catch (err) {
      request.log.warn({ err }, "guest session issuance failed");
      return reply.code(401).send();
    }
  }

  const externalToken = authHeader.slice("Bearer ".length);

  try {
    const claims = await verifyExternalToken(externalToken);
    if (await isRevoked(claims.sub)) {
      return reply.code(401).send();
    }
    const internalToken = await mintInternalToken(claims);
    reply.header("X-User-Id", claims.sub);
    reply.header("X-User-Role", claims.role);
    reply.header("X-Internal-Token", internalToken);
    return reply.code(200).send();
  } catch (err) {
    request.log.warn({ err }, "external token verification failed");
    return reply.code(401).send();
  }
});

app.listen({ port: config.port, host: "0.0.0.0" }).catch((err) => {
  app.log.error(err);
  process.exit(1);
});
