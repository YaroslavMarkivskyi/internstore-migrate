import { CurrentUser } from '../users/interfaces';

export interface AuthState {
  currentUser: CurrentUser | null;
  accessToken: string | null;
  refreshToken: string | null;
}

export interface RefreshToken {
  refresh: string;
}

export interface AccessToken {
  access: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthCredentials extends RefreshToken, AccessToken {}

export interface SignUpCredentials {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
}
