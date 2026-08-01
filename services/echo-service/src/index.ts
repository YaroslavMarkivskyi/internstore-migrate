import Fastify from "fastify";
import { createInternalTokenVerifier } from "./internalToken.js";

// Stand-in for a real domain service. Echoes back what it received from
// the Gateway (nginx + auth-backend) so the end-to-end auth flow can be
// verified without building a real downstream service yet: a successful
// request here proves X-User-Id / X-User-Role / X-Internal-Token made it
// all the way through.
//
// Critically, this service does NOT trust X-User-Id/X-User-Role headers on
// their own — anyone on the docker network could set those. It validates
// the internal token's signature and expiry itself (AUTH-03: "internal
// services validate the internal token locally and never call Keycloak"),
// and only echoes back the claims that came out of that verification.
const internalTokenSecret = process.env.INTERNAL_TOKEN_SECRET;
if (!internalTokenSecret) {
  throw new Error("Missing required env var: INTERNAL_TOKEN_SECRET");
}
const verifyInternalToken = createInternalTokenVerifier(internalTokenSecret);

const app = Fastify({ logger: true });

app.get("/health", async () => ({ status: "ok" }));

app.all("/*", async (request, reply) => {
  const internalToken = request.headers["x-internal-token"];
  if (typeof internalToken !== "string") {
    return reply.code(401).send({ error: "Missing internal token" });
  }

  try {
    const claims = await verifyInternalToken(internalToken);
    return { method: request.method, url: request.url, userId: claims.sub, userRole: claims.role };
  } catch (err) {
    request.log.warn({ err }, "internal token verification failed");
    return reply.code(401).send({ error: "Invalid internal token" });
  }
});

const port = Number(process.env.PORT ?? "4000");
app.listen({ port, host: "0.0.0.0" }).catch((err) => {
  app.log.error(err);
  process.exit(1);
});
