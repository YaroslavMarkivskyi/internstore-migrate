import Fastify from "fastify";
import { loadConfig } from "./config.js";
import { createExternalTokenVerifier } from "./auth/externalToken.js";
import { createInternalTokenIssuer } from "./auth/internalToken.js";

const config = loadConfig();
const verifyExternalToken = createExternalTokenVerifier(config.keycloakIssuer, config.keycloakJwksUri);
const mintInternalToken = createInternalTokenIssuer(config.internalTokenSecret, config.internalTokenTtlSeconds);

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

app.listen({ port: config.port, host: "0.0.0.0" }).catch((err) => {
  app.log.error(err);
  process.exit(1);
});
