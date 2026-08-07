import axios, { AxiosHeaders, InternalAxiosRequestConfig } from 'axios';

import applyCaseMiddleware from 'axios-case-converter';

import { refresh } from '@services/http/public/auth';
import {
  clearCredentials,
  getAccessToken,
  getRefreshToken,
  updateAccessToken,
} from '@store/reducers/auth';
import { store } from '@store/store';
import convertDates from '@utils/convertDates';

export const SERVER_URL =
  process.env.SERVER_URL ?? 'http://localhost:8000/api/';

const api = axios.create({
  baseURL: SERVER_URL,
  transformResponse: [
    data => {
      try {
        return JSON.parse(data, convertDates);
      } catch {
        return data;
      }
    },
  ],
  withCredentials: true,
});

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Shared across every request that 401s while a refresh is already
// in-flight -- without this, a page firing several parallel requests right
// as the access token expires triggers one refresh call *per request*
// instead of one. Besides being wasteful, this is a genuine bug: any
// Keycloak client with refresh-token rotation enabled invalidates a
// refresh token on first use, so every one of those concurrent calls
// after the first would fail outright (already-consumed token), turning a
// single ordinary token-expiry moment into a cascade of visible auth
// failures / an unwanted logout instead of one silent, transparent retry.
let refreshPromise: Promise<string | null> | null = null;

const performRefresh = async (refreshToken: string): Promise<string | null> => {
  try {
    const refreshResponse = await refresh({ refresh: refreshToken });
    if (!refreshResponse?.access) return null;
    store.dispatch(updateAccessToken(refreshResponse.access));
    return refreshResponse.access;
  } catch {
    return null;
  }
};

api.interceptors.response.use(
  resp => resp,
  async error => {
    const originalRequest = error.config;

    if (
      error.response?.status !== 401 ||
      !originalRequest ||
      originalRequest.headers?.['X-Retry']
    ) {
      return Promise.reject(error);
    }

    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      return Promise.reject(error);
    }

    if (!refreshPromise) {
      refreshPromise = performRefresh(refreshToken).finally(() => {
        refreshPromise = null;
      });
    }

    const newAccessToken = await refreshPromise;

    if (!newAccessToken) {
      // The refresh token itself is dead (expired/revoked/already
      // consumed by someone else) -- nothing left to retry with, so this
      // is a real logout rather than a transient blip. Clearing here
      // (instead of leaving stale tokens in the store) stops every other
      // still-pending request from silently repeating this exact same
      // failed refresh attempt.
      store.dispatch(clearCredentials());
      return Promise.reject(error);
    }

    // prevent infinite retrying
    const headers = new AxiosHeaders(originalRequest.headers);
    headers.set('X-Retry', 'true');
    originalRequest.headers = headers;

    // call one more time -- re-enters the request interceptor above,
    // which reads the freshly-dispatched access token from the store.
    return api(originalRequest);
  }
);

export const ccApi = applyCaseMiddleware(api, { ignoreHeaders: true });

export default api;

/**
 * Convert any flat object of primitives, arrays or File arrays into FormData.
 *
 * @param data          An object whose values are string|number|boolean,
 *                      or File[], or undefined.
 * @param fileKeys      A list of keys in `data` that should be treated as File[].
 */
export function toFormData<T extends Record<string, unknown>>(
  data: T,
  fileKeys: Array<keyof T> = []
): FormData {
  const form = new FormData();

  for (const key of Object.keys(data) as Array<keyof T>) {
    const value = data[key];
    if (value == null) continue;

    if (fileKeys.includes(key) && Array.isArray(value)) {
      for (const item of value) {
        if (item instanceof File) {
          form.append(String(key), item, item.name);
        } else {
          form.append(String(key), String(item));
        }
      }
    } else {
      form.append(String(key), String(value));
    }
  }

  return form;
}
