import { useSyncExternalStore } from 'react';

/** "done" once the tour was finished, skipped or closed (Plan 19 D12). */
export const TOUR_KEY = 'sc.tour.v1';

let doneThisLoad = false; // storage blocked: the tour still shows at most once per page load
const listeners = new Set<() => void>();

export function isTourDone(): boolean {
  if (doneThisLoad) return true;
  try {
    return localStorage.getItem(TOUR_KEY) === 'done';
  } catch {
    return false;
  }
}

export function markTourDone(): void {
  doneThisLoad = true;
  try {
    localStorage.setItem(TOUR_KEY, 'done');
  } catch {
    // Private mode or blocked storage: the in-memory flag covers this page load.
  }
  for (const listener of listeners) listener();
}

export function subscribeTour(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTourDone(): boolean {
  return useSyncExternalStore(subscribeTour, isTourDone, () => true);
}

export function resetTourForTests(): void {
  doneThisLoad = false;
  listeners.clear();
}
