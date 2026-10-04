import type { AdminEvent, AdminRosterRow, EventBody } from './api';

export interface FormValues {
  title: string;
  date: string;
  time: string;
  deadlineDate: string;
  deadlineTime: string;
  notes: string;
  capacity: string;
  allowGuests: boolean;
  maxGuests: string;
}

export const NOTES_MAX = 2000;
const COUNT = new Intl.NumberFormat('en-US');

/** 20:00 the day before the start date, the form's default deadline (§5.7.5). */
export function defaultDeadline(date: string): { date: string; time: string } {
  const [year = 1970, month = 1, day = 1] = date.split('-').map(Number);
  const before = new Date(Date.UTC(year, month - 1, day - 1));
  return { date: before.toISOString().slice(0, 10), time: '20:00' };
}

export function notesCounter(length: number): string {
  return `${COUNT.format(length)} / ${COUNT.format(NOTES_MAX)}`;
}

export function fromEvent(event: AdminEvent | null): FormValues {
  if (event === null) {
    return {
      title: '',
      date: '',
      time: '',
      deadlineDate: '',
      deadlineTime: '',
      notes: '',
      capacity: '',
      allowGuests: false,
      maxGuests: '1',
    };
  }
  return {
    title: event.title,
    date: event.local_date,
    time: event.local_time,
    deadlineDate: event.deadline_local_date,
    deadlineTime: event.deadline_local_time,
    notes: event.notes,
    capacity: event.capacity === null ? '' : String(event.capacity),
    allowGuests: event.allow_guests,
    maxGuests: String(event.allow_guests ? event.max_guests : 1),
  };
}

export function toBody(values: FormValues): EventBody {
  return {
    title: values.title.trim(),
    starts_local: `${values.date}T${values.time}`,
    deadline_local: `${values.deadlineDate}T${values.deadlineTime}`,
    notes: values.notes,
    capacity: values.capacity.trim() === '' ? null : Number(values.capacity),
    allow_guests: values.allowGuests,
    max_guests: values.allowGuests ? Number(values.maxGuests) : 0,
  };
}

/** "1 spot open; the next sign-up on the waitlist needs 3." when the waitlist head does not fit. */
export function headHint(rows: readonly AdminRosterRow[], capacity: number | null): string | null {
  if (capacity === null) return null;
  const taken = rows.filter((r) => r.status === 'going').reduce((n, r) => n + 1 + r.guests, 0);
  const head = rows
    .filter((r) => r.status === 'waitlist')
    .sort((a, b) => (a.waitlist_position ?? 0) - (b.waitlist_position ?? 0))[0];
  const open = capacity - taken;
  if (head === undefined || open <= 0 || 1 + head.guests <= open) return null;
  return `${open} spot${open === 1 ? '' : 's'} open; the next sign-up on the waitlist needs ${1 + head.guests}.`;
}

export function statusLabel(row: AdminRosterRow): string {
  switch (row.status) {
    case 'going':
      return 'Going';
    case 'waitlist':
      return `Waitlist #${row.waitlist_position ?? ''}`;
    case 'cancelled':
      return 'Cancelled';
    default:
      return 'Removed';
  }
}

export function sourceLabel(row: AdminRosterRow): string {
  return row.typed_name === null ? 'List' : 'New name';
}

/** Upcoming club events soonest first, then past ones most recent first; the split is the
 * server's `upcoming` flag, never the device clock. */
export function sortEvents(events: readonly AdminEvent[]): AdminEvent[] {
  const time = (e: AdminEvent) => Date.parse(e.starts_at);
  const upcoming = events.filter((e) => e.upcoming).sort((a, b) => time(a) - time(b));
  const past = events.filter((e) => !e.upcoming).sort((a, b) => time(b) - time(a));
  return [...upcoming, ...past];
}

/** `deadline` moved by the same number of whole days as `from` to `to` (all YYYY-MM-DD). */
export function shiftDate(deadline: string, from: string, to: string): string {
  const day = (iso: string) => {
    const [y = 1970, m = 1, d = 1] = iso.split('-').map(Number);
    return Date.UTC(y, m - 1, d);
  };
  const moved = new Date(day(deadline) + day(to) - day(from));
  return moved.toISOString().slice(0, 10);
}

export const CONTACT_SOURCES: Record<string, string> = {
  signup: 'Sign-up',
  organizer: 'Organizer',
  link: 'Linked',
};
