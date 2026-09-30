import type { EventDetail } from '../../events/api';
import { roundTypeLabel } from '../../events/format';
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
