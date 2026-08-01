import { jwtVerify } from "jose";

const ISSUER = "internstore-gateway";

export interface InternalClaims {
  sub: string;
  role: "customer" | "admin";
}

// Mirrors auth-backend's createInternalTokenVerifier (services/auth-backend/src/auth/internalToken.ts).
// Duplicated rather than shared because these are independent deployable
// services — this is the one piece of logic every domain service needs:
// validate the Gateway-minted internal token locally (HMAC), no call back
// to auth-backend or Keycloak.
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
