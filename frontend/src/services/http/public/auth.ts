import { signInWithEmailAndPassword, signOut } from 'firebase/auth';

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
  _creds: SignUpCredentials
): Promise<AuthCredentials> => {
  throw new Error(
    'Sign-up is not available yet: the backend has no user-registration endpoint.'
  );
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
