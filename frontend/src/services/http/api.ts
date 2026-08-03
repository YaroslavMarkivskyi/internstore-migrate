import axios, { AxiosHeaders, InternalAxiosRequestConfig } from 'axios';

import applyCaseMiddleware from 'axios-case-converter';

import { refresh } from '@services/http/public/auth';
import {
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

api.interceptors.response.use(
  resp => resp,
  async error => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest.headers?.['X-Retry']
    ) {
      // call refresh endpoint
      const refreshToken = getRefreshToken();

      if (!refreshToken) {
        return Promise.reject(error);
      }

      try {
        const refreshResponse = await refresh({ refresh: refreshToken });

        // Store the new access token in Redux
        if (refreshResponse && refreshResponse.access) {
          store.dispatch(updateAccessToken(refreshResponse.access));
        }

        // prevent infinite retrying
        const headers = new AxiosHeaders(originalRequest.headers);
        headers.set('X-Retry', 'true');
        originalRequest.headers = headers;

        // call one more time
        return api(originalRequest);
      } catch {
        // If refresh fails, reject with the original error
        return Promise.reject(error);
      }
    } else {
      return Promise.reject(error);
    }
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
