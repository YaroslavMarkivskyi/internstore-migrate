import { randomUUID } from "node:crypto";
import { Redis } from "ioredis";

// 7 days. Not sliding — a guest's identity expires 7 days after it was
// first created, regardless of activity in between (see plan doc, "TTL
// sliding on reuse" decision point: kept simple by design).
export const GUEST_SESSION_TTL_SECONDS = 60 * 60 * 24 * 7;

const KEY_PREFIX = "guest_session:";

export interface GuestSessionStore {
  lookup(guestId: string): Promise<boolean>;
  create(): Promise<string>;
}

// Separate from revocation.ts's Redis usage (a denylist, different concern)
// — its own key prefix so the two never collide.
export function createGuestSessionStore(redisUrl: string): GuestSessionStore {
  const redis = new Redis(redisUrl);

  return {
    async lookup(guestId: string): Promise<boolean> {
      const value = await redis.get(KEY_PREFIX + guestId);
      return value !== null;
    },

    async create(): Promise<string> {
      const guestId = randomUUID();
      await redis.set(KEY_PREFIX + guestId, "1", "EX", GUEST_SESSION_TTL_SECONDS);
      return guestId;
    },
  };
}
