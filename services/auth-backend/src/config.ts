function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required env var: ${name}`);
  }
  return value;
}

export interface GatewayConfig {
  port: number;
  keycloakIssuer: string;
  keycloakJwksUri: string;
  internalTokenSecret: string;
  internalTokenTtlSeconds: number;
  // Used by the /logout denylist (see auth/revocation.ts) and the guest
  // cart session store (see auth/guestSession.ts) — mandatory since guest
  // checkout now depends on it.
  redisUrl: string;
}

export function loadConfig(): GatewayConfig {
  return {
    port: Number(process.env.PORT ?? "3000"),
    keycloakIssuer: requireEnv("KEYCLOAK_ISSUER"),
    keycloakJwksUri: requireEnv("KEYCLOAK_JWKS_URI"),
    internalTokenSecret: requireEnv("INTERNAL_TOKEN_SECRET"),
    internalTokenTtlSeconds: Number(process.env.INTERNAL_TOKEN_TTL_SECONDS ?? "60"),
    redisUrl: requireEnv("REDIS_URL"),
  };
}
