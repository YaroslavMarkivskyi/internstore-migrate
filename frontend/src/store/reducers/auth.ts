import { createSlice, PayloadAction } from '@reduxjs/toolkit';

import { jwtDecode } from 'jwt-decode';

import { RootState, store } from '@store/store';

import { AuthCredentials, AuthState } from '../../types/auth/interfaces';
import { CurrentUser } from '../../types/users/interfaces';

interface KeycloakAccessTokenClaims {
  sub: string;
  email?: string;
  realm_access?: { roles?: string[] };
  exp?: number;
  iat?: number;
}

const decodeCurrentUser = (accessToken: string): CurrentUser | null => {
  try {
    const claims = jwtDecode<KeycloakAccessTokenClaims>(accessToken);
    return {
      user_id: claims.sub,
      email: claims.email,
      is_admin: claims.realm_access?.roles?.includes('admin') ?? false,
      exp: claims.exp,
      iat: claims.iat,
    };
  } catch {
    return null;
  }
};

const initialState: AuthState = {
  currentUser: null,
  accessToken: null,
  refreshToken: null,
};

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setCredentials: (state, action: PayloadAction<AuthCredentials>) => {
      const { access, refresh } = action.payload;
      state.currentUser = decodeCurrentUser(access);
      state.accessToken = access;
      state.refreshToken = refresh;
    },
    clearCredentials: state => {
      state.currentUser = null;
      state.accessToken = null;
      state.refreshToken = null;
    },
    updateAccessToken: (state, action: PayloadAction<string>) => {
      state.accessToken = action.payload;
      state.currentUser = decodeCurrentUser(action.payload);
    },
  },
});

export const { setCredentials, clearCredentials, updateAccessToken } =
  authSlice.actions;

export const selectRefreshToken = (state: RootState) => state.auth.refreshToken;
export const selectAccessToken = (state: RootState) => state.auth.accessToken;
export const selectCurrentUser = (state: RootState) => state.auth.currentUser;
export default authSlice.reducer;

export const getAccessToken = (): string | null =>
  store.getState().auth.accessToken;

export const getRefreshToken = (): string | null =>
  store.getState().auth.refreshToken;
