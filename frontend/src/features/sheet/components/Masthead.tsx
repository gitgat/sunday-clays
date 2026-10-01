import { Link } from 'react-router';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { formatDay } from '../../home/format';
import type { SheetIssue } from '../api';
import { ShareSheetButton } from './ShareSheetButton';

const LINK = 'inline-flex min-h-11 items-center rounded-button px-2 underline underline-offset-2';

type Newer = NonNullable<SheetIssue['masthead']['newer']>;

/** Home's Latest Sunday wording for a Sunday without full results. */
export function newerText(newer: Newer): string {
  if (newer.has_scores) return `Partial results — ${String(newer.n_shooters)} shooters so far`;
  return newer.head_count === null
    ? 'No scores recorded'
    : `Attendance only — ${String(newer.head_count)} shooters, no scores recorded`;
}

/** The latest issue points at a newer Sunday that has no full results yet. */
function NewerSunday({ newer }: { newer: Newer }) {
  const link = useRoundTypeLink(`/events/${newer.date}`);
  return (
    <p className="flex flex-wrap items-center gap-x-2 rounded-card bg-surface px-3 py-2 text-sm">
      <span>{`Newer Sunday, ${formatDay(newer.date)}: ${newerText(newer)}.`}</span>
      <Link to={link} className={LINK}>
        {`See ${formatDay(newer.date)}`}
      </Link>
    </p>
  );
}

/**
 * "THE SUNDAY SHEET", the Sunday, its issue number and the way to the other issues; on the latest
 * issue, a note about a newer Sunday that has no full results yet.
 */
export function Masthead({ issue }: { issue: SheetIssue }) {
  const { date, issue: number, previous, next, newer } = issue.masthead;
  const previousLink = useRoundTypeLink(previous === null ? '/' : `/sheet/${previous}`);
  const nextLink = useRoundTypeLink(next === null ? '/' : `/sheet/${next}`);
  const allIssues = useRoundTypeLink('/events');
  return (
    <section
      aria-labelledby="sheet-title"
      className="flex flex-col gap-2 rounded-card border-y-4 border-accent bg-elevated px-4 py-3 text-text"
    >
      <p className="text-xs uppercase tracking-widest text-text-muted">Sunday Clays</p>
      <h1 id="sheet-title" className="text-3xl font-bold uppercase tracking-wide">
        The Sunday Sheet
      </h1>
      <p className="text-sm text-text-muted">{`${formatDay(date)} · Issue ${String(number)}`}</p>
      <nav aria-label="Issues" className="-mx-2 flex flex-wrap items-center gap-x-2">
        {previous !== null && (
          <Link to={previousLink} className={LINK}>
            ← Previous issue
          </Link>
        )}
        {next !== null && (
          <Link to={nextLink} className={LINK}>
            Next issue →
          </Link>
        )}
        <Link to={allIssues} className={LINK}>
          All issues
        </Link>
      </nav>
      <ShareSheetButton issue={issue} />
      {newer !== null && <NewerSunday newer={newer} />}
    </section>
  );
}
