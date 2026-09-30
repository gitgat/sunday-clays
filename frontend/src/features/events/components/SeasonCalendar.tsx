import { Link } from 'react-router';
import { Card } from '../../../components/ui/Card';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import type { EventSummary } from '../api';
import { eventExplainers } from '../explainers';
import { About } from './About';
import { formatDay } from '../format';

const MONTH = new Intl.DateTimeFormat('en-US', { month: 'short', timeZone: 'UTC' });

/** Each cell state's look, shared by the grid and its legend so the two never drift apart. */
const CELL_STYLES = {
  scored: 'bg-primary text-text',
  unscored: 'border border-outline-variant text-text-muted',
  empty: 'opacity-40',
  other: 'border border-dashed border-outline-variant text-text-muted',
} as const;

const LEGEND: { state: keyof typeof CELL_STYLES; label: string }[] = [
  { state: 'scored', label: 'Scored' },
  { state: 'unscored', label: 'No scores' },
  { state: 'other', label: 'Other round type' },
  { state: 'empty', label: 'No Sunday on file' },
];

/** ISO dates of every Sunday in `year` (UTC arithmetic, so no DST or timezone drift). */
export function sundaysOfYear(year: number): string[] {
  const days: string[] = [];
  const d = new Date(Date.UTC(year, 0, 1));
  d.setUTCDate(d.getUTCDate() + ((7 - d.getUTCDay()) % 7));
  while (d.getUTCFullYear() === year) {
    days.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 7);
  }
  return days;
}

export function cellLabel(e: EventSummary): string {
  if (e.has_scores) return `${formatDay(e.event_date)} — ${e.n_shooters} shooters`;
  if (e.head_count !== null) {
    return `${formatDay(e.event_date)} — attendance only, ${e.head_count} shooters`;
  }
  return `${formatDay(e.event_date)} — no scores`;
}

/**
 * Decision D7: a navigation grid of 44 px date links (every Sunday of the year plus any non-Sunday
 * event date), not a data chart, so it is not wrapped in ChartFrame.
 */
export function SeasonCalendar({
  year,
  events,
  otherRoundType = [],
}: {
  year: number;
  events: EventSummary[];
  /** ISO dates of Sundays the round-type filter hides; they read "Other round type", not "No Sunday on file". */
  otherRoundType?: readonly string[];
}) {
  // Date links keep the global round-type filter (C10).
  const href = useRoundTypeHref();
  const byDate = new Map(
    events.filter((e) => e.event_date.startsWith(`${year}-`)).map((e) => [e.event_date, e]),
  );
  const hiddenByFilter = new Set(otherRoundType);
  const days = [...new Set([...sundaysOfYear(year), ...byDate.keys()])].sort();
  const months = Array.from({ length: 12 }, (_, i) => {
    const mm = String(i + 1).padStart(2, '0');
    return {
      key: mm,
      label: MONTH.format(new Date(Date.UTC(year, i, 1))),
      days: days.filter((d) => d.slice(5, 7) === mm),
    };
  });
  return (
    <Card title={`Calendar ${year}`} className="flex flex-col gap-1">
      <About explainer={eventExplainers.calendar} />
      {months.map((m) => (
        <div key={m.key} className="flex items-center gap-1">
          <span className="w-10 shrink-0 text-xs text-text-muted">{m.label}</span>
          <div className="flex flex-wrap gap-1">
            {m.days.map((day) => {
              const event = byDate.get(day);
              const dayOfMonth = Number(day.slice(8, 10));
              if (!event && hiddenByFilter.has(day)) {
                return (
                  <span
                    key={day}
                    role="img"
                    aria-label={`${formatDay(day)} — other round type`}
                    className={`flex size-11 items-center justify-center rounded-button text-sm ${CELL_STYLES.other}`}
                  >
                    {dayOfMonth}
                  </span>
                );
              }
              if (!event) {
                return (
                  <span
                    key={day}
                    aria-hidden="true"
                    className={`flex size-11 items-center justify-center text-sm ${CELL_STYLES.empty}`}
                  >
                    {dayOfMonth}
                  </span>
                );
              }
              return (
                <Link
                  key={day}
                  to={href(`/events/${day}`)}
                  aria-label={cellLabel(event)}
                  className={`flex size-11 items-center justify-center rounded-button text-sm ${
                    CELL_STYLES[event.has_scores ? 'scored' : 'unscored']
                  }`}
                >
                  {dayOfMonth}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
      <ul
        aria-label="Calendar legend"
        className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-muted"
      >
        {LEGEND.map(({ state, label }) => (
          <li key={state} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={`flex size-6 items-center justify-center rounded-button ${CELL_STYLES[state]}`}
            >
              7
            </span>
            {label}
          </li>
        ))}
      </ul>
    </Card>
  );
}
