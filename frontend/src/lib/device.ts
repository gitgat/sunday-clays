/**
 * The random id this browser sends with fist bumps (Plan 14), kept only in localStorage. It is
 * never tied to a name and goes nowhere but the bump requests.
 */
const KEY = 'sc.device';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * A random version-4 UUID. `crypto.randomUUID` exists only in secure contexts (https and
 * localhost), so a page opened over plain http on the LAN builds one from getRandomValues.
 */
export function newUuid(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  // Byte 6 carries the version (4), byte 8 the RFC 4122 variant (10xx).
  const bytes = crypto
    .getRandomValues(new Uint8Array(16))
    .map((b, i) => (i === 6 ? (b & 0x0f) | 0x40 : i === 8 ? (b & 0x3f) | 0x80 : b));
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/**
 * This browser's device id, created on first use. Null when localStorage is unavailable or does
 * not keep what is written (private mode, blocked site data): bumps then stay disabled rather
 * than sending an id that changes on every visit.
 */
export function getDeviceId(): string | null {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored !== null && UUID.test(stored)) return stored;
    const id = newUuid();
    localStorage.setItem(KEY, id);
    return localStorage.getItem(KEY) === id ? id : null;
  } catch {
    return null;
  }
}
