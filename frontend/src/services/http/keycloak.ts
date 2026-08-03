import axios from 'axios';

// Talks directly to Keycloak's token endpoint (not through the nginx
// gateway — Keycloak is exposed on its own port, see docker-compose.yml in
// internstore-migrate). The `internstore-web` client is public with
// Direct Access Grants enabled, so a plain username/password form can still
// exchange credentials for tokens without a full redirect-based OIDC flow.
const KEYCLOAK_URL = process.env.KEYCLOAK_URL ?? 'http://localhost:8081';
const KEYCLOAK_REALM = process.env.KEYCLOAK_REALM ?? 'internstore';
const KEYCLOAK_CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID ?? 'internstore-web';

const TOKEN_URL = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token`;
const LOGOUT_URL = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/logout`;

export interface KeycloakTokenResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
}

export const passwordGrant = async (
  username: string,
  password: string
): Promise<KeycloakTokenResponse> => {
  const body = new URLSearchParams({
    grant_type: 'password',
    client_id: KEYCLOAK_CLIENT_ID,
    username,
    password,
  });
  const resp = await axios.post<KeycloakTokenResponse>(TOKEN_URL, body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return resp.data;
};

export const refreshTokenGrant = async (
  refreshToken: string
): Promise<KeycloakTokenResponse> => {
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    client_id: KEYCLOAK_CLIENT_ID,
    refresh_token: refreshToken,
  });
  const resp = await axios.post<KeycloakTokenResponse>(TOKEN_URL, body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return resp.data;
};

export const revokeSession = async (refreshToken: string): Promise<void> => {
  const body = new URLSearchParams({
    client_id: KEYCLOAK_CLIENT_ID,
    refresh_token: refreshToken,
  });
  await axios.post(LOGOUT_URL, body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};
