// Decoded from a Firebase access token (sub is a UUID, not a numeric id).
export interface CurrentUser {
  user_id: string;
  email?: string;
  is_admin: boolean;
  exp?: number;
  iat?: number;
}
