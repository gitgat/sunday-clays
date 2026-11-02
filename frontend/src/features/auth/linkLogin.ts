import type { QueryClient } from '@tanstack/react-query';
import { fetchSession, linkLogin, SESSION_QUERY_KEY } from './api';

/** Cache flag read by LoginPage: a password link was tried and failed. Holds no password. */
export const LINK_FAILED_KEY = ['link-login', 'failed'] as const;

const LINK_PARAM = 'p';

export interface LinkLoginUrl {
  /** The first non-empty `p` value, decoded; null when there was none (or it was empty). */
  password: string | null;
  /** path + query + hash with every `p` parameter removed; other parameters stay byte for byte. */
  cleanedUrl: string;
}

function decodeComponent(raw: string): string {
  const spaced = raw.replace(/\+/g, ' ');
  try {
    return decodeURIComponent(spaced);
  } catch {
    return spaced;
  }
}

/** Pure: pulls the `p` password out of a URL and returns the URL without it. */
export function extractLinkPassword(url: string): LinkLoginUrl {
  const parsed = new URL(url, 'http://link.invalid');
  const kept: string[] = [];
  let password: string | null = null;
  let found = false;
  for (const part of parsed.search.slice(1).split('&')) {
    const eq = part.indexOf('=');
    const key = decodeComponent(eq === -1 ? part : part.slice(0, eq));
    if (key !== LINK_PARAM) {
      if (part !== '') kept.push(part);
      continue;
    }
    if (!found) {
      found = true;
      const value = decodeComponent(eq === -1 ? '' : part.slice(eq + 1));
      password = value === '' ? null : value;
    }
  }
  const search = kept.length > 0 ? `?${kept.join('&')}` : '';
  return { password, cleanedUrl: `${parsed.pathname}${search}${parsed.hash}` };
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
    return; // cannot tell who is signed in: send nothing, let RequireRole report it
  }
  try {
    queryClient.setQueryData(SESSION_QUERY_KEY, await linkLogin(password));
  } catch {
    queryClient.setQueryData(LINK_FAILED_KEY, true);
  }
}

/** Null when no link password is held; otherwise settles (never rejects) once resolved. */
export function resolveLinkLogin(queryClient: QueryClient): Promise<void> | null {
  const password = takePendingLinkPassword();
  return password === null ? null : run(queryClient, password);
}
