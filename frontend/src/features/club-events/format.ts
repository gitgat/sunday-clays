import type { ClubEventSummary, RosterRow } from './api';

/** Plan 20 §5.8 copy. Dates and times come from the server's club-time parts, never from a
 * timestamp read in the device's zone (D21). */
export const SWITCHED_OFF = "Club events aren't available right now. Nothing was saved.";
export const PROMOTED = "Good news: a spot opened and you're in.";
export const EMPTY_ROSTER = 'No one has signed up yet. Be the first.';
export const PURGED = 'The sign-up list was cleared 30 days after the event.';
export const CANCELLED = 'This event was cancelled by the organizers.';
export const EMAIL_HELP = 'Only organizers see it. This site never sends email.';
export const WAITLIST_WARNING = 'This will put you on the waitlist.';
export const EMAIL_ON_FILE = "We'll use the email we have for you.";

type Spots = Pick<ClubEventSummary, 'capacity' | 'spots_taken' | 'waitlist_count'>;
type When = Pick<
  ClubEventSummary,
  'local_date' | 'local_time' | 'deadline_local_date' | 'deadline_local_time' | 'state'
>;
type Mine = Pick<RosterRow, 'status' | 'guests' | 'waitlist_position'>;

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

const DATE_PARTS = new Intl.DateTimeFormat('en-US', {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
});

/** "Sat, Oct 17" from `YYYY-MM-DD`, read as a UTC calendar date, so no device zone applies. */
export function formatEventDate(localDate: string): string {
  const date = new Date(`${localDate}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? localDate : DATE_PARTS.format(date);
}

/** "11:30 PM" from `HH:MM`. */
export function formatEventTime(localTime: string): string {
  const [hour = 0, minute = 0] = localTime.split(':').map(Number);
  const twelve = hour % 12 === 0 ? 12 : hour % 12;
  return `${twelve}:${String(minute).padStart(2, '0')} ${hour < 12 ? 'AM' : 'PM'}`;
}

export function whenLine(e: Pick<ClubEventSummary, 'local_date' | 'local_time'>): string {
  return `${formatEventDate(e.local_date)} · ${formatEventTime(e.local_time)}`;
}

/** The deadline while open; afterwards what is true now; nothing for a cancelled event. */
export function deadlineLine(e: When): string | null {
  switch (e.state) {
    case 'open':
      return `Sign up by ${formatEventDate(e.deadline_local_date)}, ${formatEventTime(e.deadline_local_time)}`;
    case 'closed':
      return 'Sign-ups closed';
    case 'started':
      return 'Happening now';
    default:
      return null;
  }
}

export function spotsLine(e: Spots): string {
  if (e.capacity === null) return `${e.spots_taken} going`;
  if (e.spots_taken >= e.capacity) {
    return e.waitlist_count > 0
      ? `Full · ${e.waitlist_count} on the waitlist`
      : 'Full · join the waitlist';
  }
  return `${e.spots_taken} of ${e.capacity} spots taken`;
}

/** Below the roster: the spots line plus the waitlist when it is not already said. */
export function rosterSummary(e: Spots): string {
  const full = e.capacity !== null && e.spots_taken >= e.capacity;
  return !full && e.waitlist_count > 0
    ? `${spotsLine(e)} · ${e.waitlist_count} on the waitlist`
    : spotsLine(e);
}

export function guestsRule(e: Pick<ClubEventSummary, 'allow_guests' | 'max_guests'>): string {
  return e.allow_guests ? `Guests welcome, up to ${e.max_guests} each` : 'Members only, no guests';
}

export function statusLine(row: Mine): string {
  if (row.status === 'waitlist') {
    const place = row.waitlist_position === null ? '.' : `: #${row.waitlist_position}.`;
    return `You're on the waitlist${place} If a spot opens, you move up automatically.`;
  }
  return row.guests > 0
    ? `You're in, plus ${plural(row.guests, 'guest')}. See you there!`
    : "You're in. See you there!";
}

export function chipText(row: Mine): string {
  if (row.status === 'going') return "You're in";
  return row.waitlist_position === null ? 'On the waitlist' : `Waitlist #${row.waitlist_position}`;
}

export function cancelOwnQuestion(guests: number): string {
  return guests > 0 ? `Cancel your spot and ${plural(guests, 'guest')}?` : 'Cancel your spot?';
}

export function cameLine(e: Pick<ClubEventSummary, 'signups'>): string {
  return `${e.signups} came`;
}

export function onFileAfterRace(name: string): string {
  return `We'll use the email already on file for ${name}. To cancel, use this device or ask an organizer.`;
}
