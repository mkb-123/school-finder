/**
 * Simple fetch wrapper for calling the backend API.
 *
 * During development, Vite proxies /api/* to http://localhost:8000 so all
 * requests can use relative paths.
 */

const BASE_URL = "/api";

export interface ApiError {
  detail: string;
  status: number;
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({
      detail: response.statusText,
    }));
    throw {
      detail: body.detail ?? response.statusText,
      status: response.status,
    } as ApiError;
  }

  // Handle empty 204 No Content responses
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

/** GET request */
export function get<T>(
  endpoint: string,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  let url = endpoint;
  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        searchParams.set(key, String(value));
      }
    }
    const qs = searchParams.toString();
    if (qs) url += `?${qs}`;
  }
  return request<T>(url);
}

/** POST request */
export function post<T>(endpoint: string, body: unknown): Promise<T> {
  return request<T>(endpoint, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export default { get, post };
