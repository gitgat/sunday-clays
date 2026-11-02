import type { QueryClient } from '@tanstack/react-query';
import { ApiError } from '../../api/errors';
import { fetchSession, linkLogin, SESSION_QUERY_KEY } from './api';

/** Cache flag read by LoginPage: why a password link did not log in. Holds no password. */
export const LINK_FAILED_KEY = ['link-login', 'failed'] as const;
export type LinkFailure = 'rejected' | 'unavailable';

const LINK_PARAM = 'p';
/** The Explorer's old rain filter, written `p=0..0.25` before `?p=` became the password link. */
const LEGACY_RAIN_RANGE = /^[\d.]*\.\.[\d.]*$/;
const RAIN_PARAM = 'rain';

export interface LinkLoginUrl {
  /** The first non-empty `p` value, decoded; null when there was none (or it was empty). */
  password: string | null;
  /** path + query + hash with every `p` parameter removed; other parameters stay byte for byte. */
  cleanedUrl: string;
}

/** Splits by hand, never through `new URL`: a path starting `//` would be read as a host. */
function splitUrl(url: string): { path: string; search: string; hash: string } {
  const withoutOrigin = url.replace(/^[a-z][a-z0-9+.-]*:\/\/[^/?#]*/i, '');
  const hashAt = withoutOrigin.indexOf('#');
  const hash = hashAt === -1 ? '' : withoutOrigin.slice(hashAt);
  const rest = hashAt === -1 ? withoutOrigin : withoutOrigin.slice(0, hashAt);
  const queryAt = rest.indexOf('?');
  return {
    path: queryAt === -1 ? rest : rest.slice(0, queryAt),
    search: queryAt === -1 ? '' : rest.slice(queryAt + 1),
    hash,
  };
}

/** Pure: pulls the `p` password out of a URL and returns the URL without it. */
export function extractLinkPassword(url: string): LinkLoginUrl {
  const { path, search, hash } = splitUrl(url);
  const onExplorer = path === '/explorer' || path.startsWith('/explorer/');
  const kept: string[] = [];
  let password: string | null = null;
  let found = false;
  let changed = false;
  for (const part of search.split('&')) {
    const parsed = new URLSearchParams(part);
    const value = parsed.get(LINK_PARAM);
    if (value === null) {
      kept.push(part);
      continue;
    }
    changed = true;
    if (onExplorer && LEGACY_RAIN_RANGE.test(value)) {
      kept.push(`${RAIN_PARAM}=${part.slice(part.indexOf('=') + 1)}`);
    } else if (!found) {
      found = true;
      password = value === '' ? null : value;
    }
  }
  if (!changed) return { password: null, cleanedUrl: url };
  const query = kept.filter((part) => part !== '').join('&');
  return { password, cleanedUrl: `${path}${query === '' ? '' : `?${query}`}${hash}` };
}

// In memory only: never storage, a cookie, a query key or router state.
let pending: string | null = null;

interface BrowserLike {
  location: Pick<Location, 'pathname' | 'search' | 'hash'>;
  history: Pick<History, 'state' | 'replaceState'>;
}

/**
 * Startup, before the router or anything else reads the URL: removes `p` from the address bar
 * (replaceState, so no history entry) and holds the password in memory for resolveLinkLogin.
 */
export function captureLinkPassword(win: BrowserLike = window): void {
  const { location, history } = win;
  const current = `${location.pathname}${location.search}${location.hash}`;
  const { password, cleanedUrl } = extractLinkPassword(current);
  if (cleanedUrl !== current) history.replaceState(history.state, '', cleanedUrl);
  if (password !== null) pending = password;
}

/** Hands the held password over exactly once. */
export function takePendingLinkPassword(): string | null {
  const password = pending;
  pending = null;
  return password;
}

async function run(queryClient: QueryClient, password: string): Promise<void> {
  try {
    const existing = await queryClient.fetchQuery({
      queryKey: SESSION_QUERY_KEY,
      queryFn: fetchSession,
      staleTime: 5 * 60_000,
    });
    if (existing !== null) return; // already signed in (any role): the link is ignored
  } catch {
    // Cannot tell who is signed in: send nothing, let RequireRole report it.
    queryClient.setQueryData<LinkFailure>(LINK_FAILED_KEY, 'unavailable');
    return;
  }
  try {
    queryClient.setQueryData(SESSION_QUERY_KEY, await linkLogin(password));
  } catch (error) {
    const wrong = error instanceof ApiError && error.status === 401;
    queryClient.setQueryData<LinkFailure>(LINK_FAILED_KEY, wrong ? 'rejected' : 'unavailable');
  }
}

/** Null when no link password is held; otherwise settles (never rejects) once resolved. */
export function resolveLinkLogin(queryClient: QueryClient): Promise<void> | null {
  const password = takePendingLinkPassword();
  return password === null ? null : run(queryClient, password);
}
