import Fastify from "fastify";
import { loadConfig } from "./config.js";
import { createExternalTokenVerifier } from "./auth/externalToken.js";
import { createInternalTokenIssuer } from "./auth/internalToken.js";
import { createRevocationChecker } from "./auth/revocation.js";

const config = loadConfig();
const verifyExternalToken = createExternalTokenVerifier(config.keycloakIssuer, config.keycloakJwksUri);
const mintInternalToken = createInternalTokenIssuer(config.internalTokenSecret, config.internalTokenTtlSeconds);
const isRevoked = createRevocationChecker(config.redisUrl);

const app = Fastify({ logger: true });

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
    return reply.code(401).send();
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
