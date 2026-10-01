/** "That's me" personalization: the viewer's own shooter id, kept only in this browser. */
const KEY = 'sc.me';
/** "Not a shooter / skip" on the Sunday Sheet (Plan 14): stop asking "Which one are you?". */
const SKIP_KEY = 'sc.me.skip';

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
}

export function clearMe(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Storage unavailable: nothing to clear.
  }
}

/** True once this browser said "Not a shooter / skip". */
export function isMeSkipped(): boolean {
  try {
    return localStorage.getItem(SKIP_KEY) === '1';
  } catch {
    return false;
  }
}

export function skipMe(): void {
  try {
    localStorage.setItem(SKIP_KEY, '1');
  } catch {
    // Storage unavailable: the question comes back next visit.
  }
}
