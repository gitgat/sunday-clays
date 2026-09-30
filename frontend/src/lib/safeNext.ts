/**
 * The only way a `?next=` value becomes a navigation target (C10): a same-origin path, else '/'.
 * URLSearchParams has already decoded the value, so `?next=/%0a/evil.com` arrives as '/\n/evil.com',
 * which the URL parser turns into '//evil.com' and is therefore rejected.
 * The prefix checks run on the raw value AND on the resolved path: the URL parser removes dot
 * segments, so '/.//evil.com' (or '/%2e//evil.com', '/x/..//evil.com') resolves to '//evil.com',
 * a protocol-relative URL that the router's pushState fallback would load from another site.
 */
export function safeNext(n: string | null): string {
  if (!n || !n.startsWith('/') || n.startsWith('//') || n.startsWith('/\\')) return '/';
  try {
    const u = new URL(n, window.location.origin);
    const p = u.pathname + u.search + u.hash;
    return u.origin === window.location.origin && !p.startsWith('//') && !p.startsWith('/\\')
      ? p
      : '/';
  } catch {
    return '/';
  }
}
