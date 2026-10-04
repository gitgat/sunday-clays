import { useSyncExternalStore } from 'react';

/**
 * This device's club-event sign-ups (Plan 20 D10a): `sc.clubEvents` maps a registration id to its
 * event, its token and the status this device last saw. The token is only ever sent to cancel.
 * Every read and write is guarded: with storage blocked the pages work, and only the same-device
 * cancel is missing (the email path still works, §5.7.3).
 */
export const TOKENS_KEY = 'sc.clubEvents';
export const PAST_OPEN_KEY = 'sc.clubEvents.pastOpen';

export type SeenStatus = 'going' | 'waitlist';
export interface StoredSignup {
  eventId: number;
  token: string;
  status: SeenStatus;
  /** Set when this device last saw it on the waitlist and it is now going (the "Good news" line). */
  promoted?: true;
}
export interface DeviceSignup extends StoredSignup {
  registrationId: number;
}
type Store = Record<string, StoredSignup>;

const EMPTY: DeviceSignup[] = [];
const listeners = new Set<() => void>();
let cachedRaw: string | null = null;
let cached: DeviceSignup[] = EMPTY;

function isSignup(value: unknown): value is StoredSignup {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.eventId === 'number' &&
    typeof v.token === 'string' &&
    (v.status === 'going' || v.status === 'waitlist')
  );
}

function rawStore(): string | null {
  try {
    return localStorage.getItem(TOKENS_KEY);
  } catch {
    return null;
  }
}

function parse(raw: string | null): Store {
  if (raw === null) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null) return {};
    return Object.fromEntries(Object.entries(parsed).filter(([, v]) => isSignup(v))) as Store;
  } catch {
    return {};
  }
}

function write(store: Store): void {
  try {
    localStorage.setItem(TOKENS_KEY, JSON.stringify(store));
  } catch {
    // storage blocked or full: the same-device cancel is unavailable, nothing else changes
  }
  listeners.forEach((listener) => {
    listener();
  });
}

function snapshot(): DeviceSignup[] {
  const raw = rawStore();
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    const entries = Object.entries(parse(raw));
    cached =
      entries.length === 0
        ? EMPTY
        : entries.map(([id, s]) => ({ ...s, registrationId: Number(id) }));
  }
  return cached;
}

export function allSignups(): DeviceSignup[] {
  return snapshot();
}

export function signupsFor(eventId: number): DeviceSignup[] {
  return snapshot().filter((s) => s.eventId === eventId);
}

export function saveSignup(registrationId: number, signup: StoredSignup): void {
  write({ ...parse(rawStore()), [String(registrationId)]: signup });
}

export function forgetSignup(registrationId: number): void {
  write(
    Object.fromEntries(
      Object.entries(parse(rawStore())).filter(([id]) => id !== String(registrationId)),
    ),
  );
}

export function forgetEvent(eventId: number): void {
  write(
    Object.fromEntries(Object.entries(parse(rawStore())).filter(([, s]) => s.eventId !== eventId)),
  );
}

/** Drops tokens for events the list no longer shows, and for purged ones (D16: the token goes with
 * the sign-up list). Called once a list read resolves, so stale tokens never outlive the list. */
export function pruneTo(eventIds: Iterable<number>, purgedIds: Iterable<number>): void {
  const known = new Set(eventIds);
  const purged = new Set(purgedIds);
  const store = parse(rawStore());
  const next = Object.fromEntries(
    Object.entries(store).filter(([, s]) => known.has(s.eventId) && !purged.has(s.eventId)),
  );
  if (Object.keys(next).length !== Object.keys(store).length) write(next);
}

/** The ids `pruneTo` wants from a list read. */
export function pruneToList(list: {
  upcoming: readonly { id: number; purged: boolean }[];
  past: readonly { id: number; purged: boolean }[];
}): void {
  const all = [...list.upcoming, ...list.past];
  pruneTo(
    all.map((e) => e.id),
    all.filter((e) => e.purged).map((e) => e.id),
  );
}

/**
 * Keeps this event's tokens in step with its roster: a sign-up no longer listed (cancelled
 * elsewhere, removed, purged) is dropped, and each one's status is recorded. Returns whether one
 * moved from the waitlist to going since this device last looked.
 */
export function reconcile(
  eventId: number,
  roster: readonly { registration_id: number; status: SeenStatus }[],
): boolean {
  let promoted = false;
  const next: Store = {};
  for (const [id, signup] of Object.entries(parse(rawStore()))) {
    if (signup.eventId !== eventId) {
      next[id] = signup;
      continue;
    }
    const row = roster.find((r) => r.registration_id === Number(id));
    if (row === undefined) continue;
    const moved = signup.status === 'waitlist' && row.status === 'going';
    promoted ||= moved;
    next[id] = moved
      ? { ...signup, status: row.status, promoted: true }
      : { ...signup, status: row.status };
  }
  write(next);
  return promoted;
}

/** Clears the "Good news" mark once the page that showed it goes away. In development,
 * React's StrictMode runs this cleanup once at mount, so the line may not show there; production
 * runs it only when the page unmounts. */
export function acknowledgePromotions(eventId: number): void {
  const next: Store = {};
  for (const [id, signup] of Object.entries(parse(rawStore()))) {
    next[id] =
      signup.eventId === eventId
        ? { eventId: signup.eventId, token: signup.token, status: signup.status }
        : signup;
  }
  write(next);
}

export function subscribeSignups(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** This device's sign-ups, re-rendering whenever a token is saved, dropped or reconciled. */
export function useDeviceSignups(): DeviceSignup[] {
  return useSyncExternalStore(subscribeSignups, snapshot, () => EMPTY);
}

export function readPastOpen(): boolean {
  try {
    return localStorage.getItem(PAST_OPEN_KEY) === '1';
  } catch {
    return false;
  }
}

export function writePastOpen(open: boolean): void {
  try {
    localStorage.setItem(PAST_OPEN_KEY, open ? '1' : '0');
  } catch {
    // a per-device convenience only
  }
}
