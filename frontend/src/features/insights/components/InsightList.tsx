import type { Insight } from '../api';
import { InsightCard } from './InsightCard';

/** "That's me" is the single shooter this insight is about: it reads in the second person. */
export function isMine(insight: Insight, meId: number | null | undefined): boolean {
  return meId != null && insight.subject_type === 'shooter' && insight.subject_id === String(meId);
}

// Literal class names so Tailwind keeps them: one column on a phone, a row on desktop (spec §3.8).
const COLUMNS = {
  1: 'flex min-w-0 flex-col gap-3',
  2: 'grid min-w-0 gap-3 lg:grid-cols-2',
  3: 'grid min-w-0 gap-3 lg:grid-cols-3',
  4: 'grid min-w-0 gap-3 lg:grid-cols-4',
} as const;

/** A feed's cards in order. */
export function InsightList({
  items,
  you = false,
  meId = null,
  label,
  columns = 1,
  wideFirst = false,
}: {
  items: readonly Insight[];
  /** Every card is about the viewer (their own profile). */
  you?: boolean;
  /** On shared pages, the viewer's own single-shooter cards read in the second person. */
  meId?: number | null;
  label: string;
  /** Cards per row on desktop. */
  columns?: keyof typeof COLUMNS;
  /** The first card (a pinned line) spans the whole row on desktop. */
  wideFirst?: boolean;
}) {
  if (items.length === 0) return null;
  return (
    <ul aria-label={label} className={COLUMNS[columns]}>
      {items.map((i, index) => (
        <InsightCard
          key={i.key}
          insight={i}
          you={you || isMine(i, meId)}
          className={wideFirst && index === 0 ? 'lg:col-span-full' : ''}
        />
      ))}
    </ul>
  );
}
