/** "That's me" personalization: the viewer's own shooter id, kept only in this browser. */
const KEY = 'sc.me';

export function getMe(): number | null {
  try {
    const raw = localStorage.getItem(KEY);
    const id = raw === null ? NaN : Number(raw);
    return Number.isInteger(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}

export function setMe(id: number): void {
  try {
    localStorage.setItem(KEY, String(id));
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
