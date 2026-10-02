import { Link } from 'react-router';
import { useRoundTypeHref } from '../../../lib/roundTypes';
import type { EventSummary } from '../api';
import {
  formatDay,
  formatScore,
  isSpecial,
  roundTypeLabel,
  specialName,
  specialTag,
} from '../format';

export function summaryLine(e: EventSummary): string {
  if (isSpecial(e)) {
    const name = specialName(e);
    return [...(name === null ? [] : [name]), specialTag(e), `${e.n_shooters} shooters`].join(
      ' · ',
    );
  }
  if (!e.has_scores) {
    return e.head_count === null
      ? 'No scores recorded'
      : `Attendance only · ${e.head_count} shooters`;
  }
  const parts = [`${e.n_shooters} shooters`, roundTypeLabel(e.round_type)];
  if (e.median !== null) parts.push(`median ${formatScore(e.median)}`);
  if (e.top_score !== null) parts.push(`top ${e.top_score}`);
  return parts.join(' · ');
}

export function EventList({ year, events }: { year: number; events: EventSummary[] }) {
  // Event links keep the global round-type filter (C10).
  const href = useRoundTypeHref();
  const sorted = [...events].sort((a, b) => b.event_date.localeCompare(a.event_date));
  return (
    <ol
      aria-label={`Sundays in ${year}`}
      className="flex flex-col divide-y divide-outline-variant rounded-card bg-elevated"
    >
      {sorted.map((e) => (
        <li key={e.event_date}>
          <Link
            to={href(`/events/${e.event_date}`)}
            className="flex min-h-11 flex-wrap items-center justify-between gap-x-3 px-4 py-2"
          >
            <span className="font-medium">{formatDay(e.event_date)}</span>
            <span className="text-sm text-text-muted">{summaryLine(e)}</span>
          </Link>
        </li>
      ))}
    </ol>
  );
}
