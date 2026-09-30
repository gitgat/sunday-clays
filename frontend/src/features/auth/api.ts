import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { api, unwrap } from '../../api/client';
import { ApiError, toApiError } from '../../api/errors';

/** Exactly two roles (Global Constraints); admin ⊇ viewer. */
export type Role = 'viewer' | 'admin';

export interface Session {
  role: Role;
}

export const SESSION_QUERY_KEY = ['/api/auth/me'] as const;

const toRole = (role: unknown): Role => (role === 'admin' ? 'admin' : 'viewer');

/** GET /api/auth/me: the session, or null when logged out (401). Other failures throw ApiError. */
export async function fetchSession(): Promise<Session | null> {
  const { data, error, response } = await api.GET('/api/auth/me');
  if (response.status === 401) return null;
  if (!response.ok) throw toApiError(response.status, error);
  return { role: toRole(data?.role) };
}

export function useSession() {
  const query = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: fetchSession,
    staleTime: 5 * 60_000,
  });
  return {
    session: query.data ?? null,
    isPending: query.isPending,
    error: query.error,
    refetch: query.refetch,
  };
}

/** Drops every cached query except the session, so one session's data never shows in another. */
function removeSessionData(queryClient: QueryClient): void {
  queryClient.removeQueries({
    predicate: (query) => query.queryKey[0] !== SESSION_QUERY_KEY[0],
  });
}

/**
 * POST /api/auth/login; on success the previous session's cached data is dropped and the session
 * query holds the new role. `gcTime: 0` drops the mutation (whose variables are the plaintext
 * password) from the MutationCache as soon as the login page unmounts.
 */
export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (password: string): Promise<Session> => {
      const data = await unwrap(api.POST('/api/auth/login', { body: { password } }));
      return { role: toRole(data.role) };
    },
    gcTime: 0,
    onSuccess: (session) => {
      removeSessionData(queryClient);
      queryClient.setQueryData(SESSION_QUERY_KEY, session);
    },
  });
}

/**
 * POST /api/auth/logout. Cached data is dropped either way. The session is marked logged out
 * (RequireRole then sends the browser to /login) only when the server cleared the cookie (2xx) or
 * says there is no session (401): the cookie is httpOnly and only the server can clear it, so after
 * any other failure the session stays and AccountPanel says the logout failed.
 */
export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/auth/logout')),
    onSettled: (_data, error) => {
      removeSessionData(queryClient);
      if (error === null || (error instanceof ApiError && error.status === 401)) {
        queryClient.setQueryData(SESSION_QUERY_KEY, null);
      }
    },
  });
}

/**
 * The redirect the API client runs when a data request gets a 401 (App.tsx passes it to
 * setNavigate). The server has just said the session is gone, so the cached session is cleared
 * first; otherwise LoginPage would see the stale role and bounce straight back, looping.
 */
export function onSessionExpired(
  queryClient: QueryClient,
  navigate: (to: string) => void,
): (to: string) => void {
  return (to) => {
    queryClient.setQueryData(SESSION_QUERY_KEY, null);
    navigate(to);
  };
}
