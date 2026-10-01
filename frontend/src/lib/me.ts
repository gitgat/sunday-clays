/** "That's me" personalization: the viewer's own shooter id, kept only in this browser. */
const KEY = 'sc.me';
/** "Skip, I’m not a shooter" on Home (Plan 15): stop asking "Which one are you?". */
const SKIP_KEY = 'sc.me.skip';

const listeners = new Set<() => void>();
/** A skip this browser could not store: still true for this page view, so every card agrees. */
let skippedInMemory = false;

/** Test-only: forget the in-memory skip so module state cannot leak between tests. */
export function resetMeForTests(): void {
  skippedInMemory = false;
}

function changed(): void {
  listeners.forEach((l) => {
    l();
  });
}

/** For `useSyncExternalStore`: called when the skip state changes (skip or pick). */
export function subscribeMe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getMe(): number | null {
  try {
    const raw = localStorage.getItem(KEY);
    const id = raw === null ? NaN : Number(raw);
    return Number.isInteger(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}

/** Remembers the viewer's shooter; picking someone also undoes an earlier skip. */
export function setMe(id: number): void {
  try {
    localStorage.setItem(KEY, String(id));
    localStorage.removeItem(SKIP_KEY);
  } catch {
    // Storage unavailable (private mode, quota): personalization is best-effort.
  }
  skippedInMemory = false;
  changed();
}

export function clearMe(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Storage unavailable: nothing to clear.
  }
}

/** True once this browser said "Skip, I’m not a shooter". */
export function isMeSkipped(): boolean {
  try {
    return localStorage.getItem(SKIP_KEY) === '1' || skippedInMemory;
  } catch {
    return skippedInMemory;
  }
}

export function skipMe(): void {
  try {
    localStorage.setItem(SKIP_KEY, '1');
  } catch {
    // Storage unavailable: the question comes back next visit.
    skippedInMemory = true;
  }
  changed();
}
