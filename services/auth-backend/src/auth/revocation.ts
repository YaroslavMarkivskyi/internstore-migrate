// Placeholder for the token-denylist check that ships with /logout
// (AUTH-05). Not wired to Redis yet — always reports "not revoked" so the
// call site in externalToken verification is already in place and doesn't
// need to change when the real check lands.
export function createRevocationChecker(redisUrl?: string) {
  return async function isRevoked(_sub: string): Promise<boolean> {
    void redisUrl;
    return false;
  };
}
