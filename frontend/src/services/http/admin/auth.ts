import { jwtDecode } from 'jwt-decode';

import { login } from '@services/http/public/auth';

import {
  AuthCredentials,
  LoginCredentials,
} from '../../../types/auth/interfaces';

interface KeycloakClaims {
  realm_access?: { roles?: string[] };
}

// There's no separate admin-login endpoint — admin is just a realm role on
// the same Keycloak account. Reuse the customer login flow, then reject
// here if the token doesn't carry the `admin` role.
export const adminLogin = async (
  creds: LoginCredentials
): Promise<AuthCredentials> => {
  const response = await login(creds);
  const claims = jwtDecode<KeycloakClaims>(response.access);
  if (!claims.realm_access?.roles?.includes('admin')) {
    throw new Error('This account does not have admin access.');
  }
  return response;
};
