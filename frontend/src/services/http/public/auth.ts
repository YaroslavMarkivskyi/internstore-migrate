import { signInWithEmailAndPassword, signOut } from 'firebase/auth';

import api from '@services/http/api';
import { auth } from '@services/firebase/client';

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
  const { user } = await signInWithEmailAndPassword(
    auth,
    creds.email,
    creds.password
  );
  const access = await user.getIdToken();
  return { access, refresh: user.refreshToken };
};

export const signUp = async (
  creds: SignUpCredentials
): Promise<AuthCredentials> => {
  // auth-backend creates the Firebase user and sets its role claim
  // (POST /api/auth/register); then we sign in normally to get tokens.
  await api.post('auth/register', creds);
  return login({ email: creds.email, password: creds.password });
};

export const logout = async (_creds: RefreshToken): Promise<void> => {
  await signOut(auth);
};

export const refresh = async (_creds: RefreshToken): Promise<AccessToken> => {
  await auth.authStateReady();
  if (!auth.currentUser) {
    throw new Error('No signed-in Firebase user to refresh.');
  }
  const access = await auth.currentUser.getIdToken(true);
  return { access };
};
