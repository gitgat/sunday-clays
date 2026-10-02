import type { EventDetail } from '../../events/api';
import { isSpecial, roundTypeLabel, specialLine, targetsOf } from '../../events/format';
import { formatFullDay } from '../format';

export const TOP_RESULTS = 5;

/**
 * A compact, image-friendly results card for one Sunday: the top 5 best rounds by rank. Plain
 * inline colours come from theme tokens only; no external fonts or images (the CSP allows none).
 */
export function EventShareCard({ event }: { event: EventDetail }) {
  const top = event.results
    .flatMap((r) =>
      r.is_best_round && r.event_rank !== null ? [{ ...r, rank: r.event_rank }] : [],
    )
    .sort((a, b) => a.rank - b.rank || a.display_name.localeCompare(b.display_name))
    .slice(0, TOP_RESULTS);
  if (isSpecial(event)) return <SpecialShareCard event={event} />;
  return (
    <article className="flex flex-col gap-2 rounded-card bg-surface p-4 text-text">
      <p className="text-sm text-accent">Sunday Clays</p>
      <h3 className="text-xl font-bold">{formatFullDay(event.event_date)}</h3>
      {event.has_scores ? (
        <>
          <p className="text-text-muted">
            {roundTypeLabel(event.round_type)} · {event.n_shooters} shooters
            {event.median === null ? '' : ` · median ${event.median}`}
          </p>
          <ol className="flex flex-col gap-1">
            {top.map((r) => (
              <li key={r.round_id} className="flex justify-between gap-4">
                <span>
                  {r.rank}. {r.display_name}
                </span>
                <span className="font-medium">{r.score}</span>
              </li>
            ))}
          </ol>
        </>
      ) : (
        <p>
          {event.head_count === null
            ? 'No scores recorded.'
            : `Attendance only: ${event.head_count} shooters, no scores recorded.`}
        </p>
      )}
    </article>
  );
}

/** A special shoot: its label and total from data, and the scores as entered (nobody is ranked). */
function SpecialShareCard({ event }: { event: EventDetail }) {
  const total = targetsOf(event);
  const top = event.results
    .filter((r) => r.is_best_round)
    .sort(
      (a, b) =>
        b.score - a.score || a.display_name.localeCompare(b.display_name) || a.ordinal - b.ordinal,
    )
    .slice(0, TOP_RESULTS);
  return (
    <article className="flex flex-col gap-2 rounded-card bg-surface p-4 text-text">
      <p className="text-sm text-accent">Sunday Clays</p>
      <h3 className="text-xl font-bold">{formatFullDay(event.event_date)}</h3>
      <p className="text-text-muted">{`${specialLine(event)} · ${event.n_shooters} shooters`}</p>
      <ol className="flex flex-col gap-1">
        {top.map((r) => (
          <li key={r.round_id} className="flex justify-between gap-4">
            <span>{r.display_name}</span>
            <span className="font-medium">{`${r.score} of ${total}`}</span>
          </li>
        ))}
      </ol>
    </article>
  );
}
