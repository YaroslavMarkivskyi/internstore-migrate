import { SignJWT, jwtVerify } from "jose";
import type { ExternalClaims } from "./externalToken.js";

const ISSUER = "internstore-gateway";

export function createInternalTokenIssuer(secret: string, ttlSeconds: number) {
  const key = new TextEncoder().encode(secret);

  return async function mintInternalToken(claims: ExternalClaims): Promise<string> {
    return new SignJWT({ role: claims.role })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuer(ISSUER)
      .setSubject(claims.sub)
      .setIssuedAt()
      .setExpirationTime(`${ttlSeconds}s`)
      .sign(key);
  };
}

export interface InternalClaims {
  sub: string;
  role: "customer" | "admin";
}

// Used by internal services to validate the Gateway-minted token locally,
// with no call back to Keycloak or the Gateway.
export function createInternalTokenVerifier(secret: string) {
  const key = new TextEncoder().encode(secret);

  return async function verifyInternalToken(token: string): Promise<InternalClaims> {
    const { payload } = await jwtVerify(token, key, { issuer: ISSUER });
    const role = payload.role;
    if (!payload.sub || (role !== "customer" && role !== "admin")) {
      throw new Error("Invalid internal token claims");
    }
    return { sub: payload.sub, role };
  };
}
