export const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';
export const PHONE_QUERY = '(max-width: 640px)';

/** The first `[data-tour=id]` element in document order with a non-zero box, or null. */
export function firstVisible(id: string): HTMLElement | null {
  for (const el of document.querySelectorAll<HTMLElement>(`[data-tour="${id}"]`)) {
    const box = el.getBoundingClientRect();
    if (box.width > 0 && box.height > 0) return el;
  }
  return null;
}
