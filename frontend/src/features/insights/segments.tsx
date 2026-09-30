import { Link } from 'react-router';
import { useRoundTypeLink } from '../../lib/roundTypes';
import type { InsightSegment } from './api';

/** A name in a headline: its profile, keeping the global round-type filter (C10). */
function ShooterName({ id, name }: { id: number; name: string }) {
  const to = useRoundTypeLink(`/shooters/${String(id)}`);
  return (
    <Link
      to={to}
      className="-mx-2 -my-3.5 px-2 py-3.5 font-medium text-text underline decoration-outline-variant underline-offset-2 hover:text-accent"
    >
      {name}
    </Link>
  );
}

/**
 * Renders a headline's typed segments (spec §3.5): names are profile links, numbers stand out,
 * everything is text. Never HTML: every value goes through React as a string.
 */
export function Segments({ segments }: { segments: readonly InsightSegment[] }) {
  return (
    <>
      {segments.map((s, i) => {
        const key = `${String(i)}-${s.t}`;
        if (s.t === 'shooter' && s.id !== undefined && s.id !== null) {
          return <ShooterName key={key} id={s.id} name={s.v} />;
        }
        if (s.t === 'num') {
          return (
            <strong key={key} className="font-medium tabular-nums">
              {s.v}
            </strong>
          );
        }
        if (s.t === 'trophy') {
          return (
            <em key={key} className="not-italic font-medium">
              {s.v}
            </em>
          );
        }
        return <span key={key}>{s.v}</span>;
      })}
    </>
  );
}

/** The plain text of segments (aria labels, tests). */
export function segmentsText(segments: readonly InsightSegment[]): string {
  return segments.map((s) => s.v).join('');
}
