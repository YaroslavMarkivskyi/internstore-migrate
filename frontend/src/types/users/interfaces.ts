// Decoded from a Keycloak access token (sub is a UUID, not a numeric id —
// see internstore-migrate/keycloak/realm-export.json).
export interface CurrentUser {
  user_id: string;
  email?: string;
  is_admin: boolean;
  exp?: number;
  iat?: number;
}
