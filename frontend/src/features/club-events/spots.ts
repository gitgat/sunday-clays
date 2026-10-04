import type { ClubEventSummary } from './api';

/**
 * The server's admit rule (domain/club_events.py `admit`, D9), mirrored for the sheet's "This
 * will put you on the waitlist." line. admitCases.json is tested against both.
 */
export function wouldWaitlist(
  e: Pick<ClubEventSummary, 'capacity' | 'spots_taken' | 'waitlist_count'>,
  newSpots: number,
): boolean {
  if (e.capacity === null) return false;
  return e.waitlist_count > 0 || e.spots_taken + newSpots > e.capacity;
}
