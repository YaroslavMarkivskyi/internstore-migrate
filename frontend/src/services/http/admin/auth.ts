import { jwtDecode } from 'jwt-decode';

import { login } from '@services/http/public/auth';

import {
  AuthCredentials,
  LoginCredentials,
} from '../../../types/auth/interfaces';

interface FirebaseAccessTokenClaims {
  role?: string;
}

// There's no separate admin-login endpoint -- admin is just a custom claim
// on the same Firebase account. Reuse the customer login flow, then reject
// here if the token doesn't carry the `admin` role.
export const adminLogin = async (
  creds: LoginCredentials
): Promise<AuthCredentials> => {
  const response = await login(creds);
  const claims = jwtDecode<FirebaseAccessTokenClaims>(response.access);
  if (claims.role !== 'admin') {
    throw new Error('This account does not have admin access.');
  }
  return response;
};
