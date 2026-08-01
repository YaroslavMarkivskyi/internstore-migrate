import { createRemoteJWKSet, jwtVerify } from "jose";
import type { JWTPayload } from "jose";

export interface ExternalClaims {
  sub: string;
  email?: string;
  role: "customer" | "admin";
}

interface KeycloakPayload extends JWTPayload {
  email?: string;
  realm_access?: { roles?: string[] };
}

// createRemoteJWKSet caches keys in-process and only refetches on an
// unrecognized `kid`, so verification never blocks on a call to Keycloak.
export function createExternalTokenVerifier(issuer: string, jwksUri: string) {
  const jwks = createRemoteJWKSet(new URL(jwksUri));

  return async function verifyExternalToken(token: string): Promise<ExternalClaims> {
    const { payload } = await jwtVerify<KeycloakPayload>(token, jwks, { issuer });

    if (!payload.sub) {
      throw new Error("Token missing sub claim");
    }

    const roles = payload.realm_access?.roles ?? [];
    const role = roles.includes("admin") ? "admin" : roles.includes("customer") ? "customer" : undefined;
    if (!role) {
      throw new Error("Token missing customer/admin role");
    }

    return { sub: payload.sub, email: payload.email, role };
  };
}
