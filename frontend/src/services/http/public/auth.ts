import {
  passwordGrant,
  refreshTokenGrant,
  revokeSession,
} from '@services/http/keycloak';

import {
  AccessToken,
  AuthCredentials,
  LoginCredentials,
  RefreshToken,
  SignUpCredentials,
} from '../../../types/auth/interfaces';

export const login = async (
  creds: LoginCredentials
): Promise<AuthCredentials> => {
  const token = await passwordGrant(creds.email, creds.password);
  return { access: token.access_token, refresh: token.refresh_token };
};

// Keycloak's `internstore-web` realm has no open self-registration endpoint
// (see keycloak/realm-export.json in internstore-migrate) — only the two
// seed users exist. Registration isn't wired up backend-side yet.
export const signUp = async (
  _creds: SignUpCredentials
): Promise<AuthCredentials> => {
  throw new Error(
    'Sign-up is not available yet: the backend has no user-registration endpoint.'
  );
};

export const logout = async (creds: RefreshToken): Promise<void> => {
  await revokeSession(creds.refresh);
};

export const refresh = async (creds: RefreshToken): Promise<AccessToken> => {
  const token = await refreshTokenGrant(creds.refresh);
  return { access: token.access_token };
};
