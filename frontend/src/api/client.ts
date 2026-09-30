import createClient, { type Middleware } from 'openapi-fetch';
import { toApiError } from './errors';
import type { paths } from './schema';

// `fetch` is looked up per request (not captured once at import) so MSW's patched fetch is used in
// tests; in browsers this is the same global fetch.
export const api = createClient<paths>({
  baseUrl: '',
  credentials: 'include',
  fetch: (request) => globalThis.fetch(request),
});

/** 401s from these endpoints are answers (logged out / wrong password), not expired sessions. */
const NO_LOGIN_REDIRECT = new Set(['/api/auth/me', '/api/auth/login', '/api/auth/logout']);

export function shouldRedirectToLogin(
  status: number,
  schemaPath: string,
  pathname: string,
): boolean {
  return status === 401 && !NO_LOGIN_REDIRECT.has(schemaPath) && pathname !== '/login';
}

/** The login URL for the current page; `next` is built only from pathname + search (C10). */
export function loginPath(): string {
  const next = window.location.pathname + window.location.search;
  return `/login?next=${encodeURIComponent(next)}`;
}

type Navigate = (to: string) => void;

let navigate: Navigate = (to) => {
  window.location.assign(to);
};

/** App.tsx routes the redirect through the data router so the SPA is not reloaded. */
export function setNavigate(fn: Navigate): void {
  navigate = fn;
}

const redirectOn401: Middleware = {
  onResponse({ response, schemaPath }) {
    if (shouldRedirectToLogin(response.status, schemaPath, window.location.pathname)) {
      navigate(loginPath());
    }
    return undefined;
  },
};

api.use(redirectOn401);

export interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/**
 * Resolves to the response data. Throws ApiError for every non-2xx response; network errors (the
 * fetch TypeError) propagate unchanged.
 */
export async function unwrap<T>(request: Promise<FetchResult<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok) throw toApiError(response.status, error);
  return data as T;
}
