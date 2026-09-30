import { useYearBoard, type LeaderboardMetric } from '../api';
import { YirLink } from './YirLink';

export const LEADERS_SHOWN = 5;

/** The top of one calendar-year leaderboard for the review year. */
export function LeaderList({
  title,
  metric,
  asOf,
  year,
  digits = 0,
}: {
  title: string;
  metric: LeaderboardMetric;
  asOf: string | undefined;
  year: number;
  digits?: number;
}) {
  const query = useYearBoard(metric, asOf);
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <h3 className="font-medium">{title}</h3>
      {query.isPending ? (
        <p role="status">Loading {title}…</p>
      ) : query.isError ? (
        <p role="alert">Could not load {title}.</p>
      ) : query.data.rows.length === 0 ? (
        <p className="text-text-muted">Nobody qualifies yet.</p>
      ) : (
        <ol aria-label={title} className="flex flex-col">
          {query.data.rows.slice(0, LEADERS_SHOWN).map((row) => (
            <li key={row.shooter_id} className="flex items-center justify-between gap-2">
              <YirLink to={`/yir/${year}/shooters/${row.shooter_id}`} className="min-w-0">
                {row.rank}. {row.display_name}
              </YirLink>
              <span>{row.value.toFixed(digits)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
