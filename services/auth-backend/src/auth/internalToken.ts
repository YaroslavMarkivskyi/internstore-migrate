import { SignJWT, jwtVerify } from "jose";

const ISSUER = "internstore-gateway";

// Narrower than ExternalClaims: only what minting actually needs. Guests
// never present a Keycloak token, so there's no ExternalClaims for them —
// this shape lets the guest branch in index.ts mint a token without
// fabricating a fake external-claims object.
export interface MintableClaims {
  sub: string;
  role: "customer" | "admin" | "guest";
}

export function createInternalTokenIssuer(secret: string, ttlSeconds: number) {
  const key = new TextEncoder().encode(secret);

  return async function mintInternalToken(claims: MintableClaims): Promise<string> {
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
  role: "customer" | "admin" | "guest";
}

// Used by internal services to validate the Gateway-minted token locally,
// with no call back to Keycloak or the Gateway.
export function createInternalTokenVerifier(secret: string) {
  const key = new TextEncoder().encode(secret);

  return async function verifyInternalToken(token: string): Promise<InternalClaims> {
    const { payload } = await jwtVerify(token, key, { issuer: ISSUER });
    const role = payload.role;
    if (!payload.sub || (role !== "customer" && role !== "admin" && role !== "guest")) {
      throw new Error("Invalid internal token claims");
    }
    return { sub: payload.sub, role };
  };
}
