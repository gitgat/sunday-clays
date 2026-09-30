import { PageTopSlot } from '../../../components/layout/pageTop';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import {
  useMeta,
  usePageDefaultWindow,
  useTimeWindow,
  type WindowRange,
} from '../../../lib/timeWindow';
import { useLegacyParams } from '../../../lib/useLegacyParams';
import { convertLegacyRecords } from '../../competition/legacyParams';
import { WidenWindow } from '../../competition/WidenWindow';
import { windowInWords, windowTag } from '../../competition/windowText';
import { useRecords, type RecordsOut } from '../api';
import {
  BiggestAdjusted,
  BiggestJumps,
  HighestRatings,
  HighestScores,
  PerfectRounds,
  ShooterRecordChart,
  type ListSize,
} from '../components/RecordSections';
import type { RecordsRange } from '../explainers';

/** The window's first day: the first Sunday ever shot when it has no lower bound (All time). */
function windowStart(range: WindowRange, firstSunday: string | null): string {
  return range.from ?? firstSunday ?? range.to;
}

export function RecordsPage() {
  const meta = useMeta().data;
  const pageDefault = usePageDefaultWindow();
  const legacy = useLegacyParams((params) =>
    convertLegacyRecords(params, {
      firstSunday: meta?.first_event_date ?? null,
      lastSunday: meta?.last_score_date ?? null,
      pageDefault,
    }),
  );
  const { window: timeWindow, range } = useTimeWindow();
  const since = range?.from ?? null;
  const asOf = range?.to ?? null;
  const records = useRecords({ since, asOf, enabled: !legacy && range !== null });
  const data = records.data;
  const scope = { since, asOf };
  const tag =
    range === null
      ? ''
      : windowTag(
          timeWindow,
          windowStart(range, meta?.first_event_date ?? null),
          range.to,
          meta?.last_score_date ?? null,
        );
  const rangeForExplainers: RecordsRange | null =
    range === null ? null : { ...(since === null ? {} : { since }), asOf: range.to };
  // The server sends every list's size; a missing key reads as empty.
  const size = (d: RecordsOut, list: string): ListSize => ({
    total: d.totals[list] ?? 0,
    tiedMore: d.tied_more[list] ?? 0,
  });

  let content;
  if (legacy) {
    content = <Skeleton label="Loading records" lines={6} />;
  } else if (records.isError) {
    content = <EmptyState title="Records unavailable" description="Try again in a moment." />;
  } else if (data === undefined || rangeForExplainers === null) {
    content = <Skeleton label="Loading records" lines={6} />;
  } else if (size(data, 'highest_scores').total === 0) {
    // No round was shot in the window: never fall back to all-time records under a windowed tag.
    content = (
      <EmptyState
        title={`No scored rounds in ${windowInWords(timeWindow)}`}
        description="Widen the window to see records."
        action={<WidenWindow />}
      />
    );
  } else {
    content = (
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <HighestScores
          rows={data.highest_scores}
          period={tag}
          size={size(data, 'highest_scores')}
          scope={scope}
          range={rangeForExplainers}
        />
        <PerfectRounds
          rows={data.perfect_rounds}
          period={tag}
          size={size(data, 'perfect_rounds')}
          scope={scope}
        />
        <BiggestAdjusted
          rows={data.biggest_adjusted}
          period={tag}
          size={size(data, 'biggest_adjusted')}
          scope={scope}
        />
        <BiggestJumps
          rows={data.biggest_jumps}
          period={tag}
          size={size(data, 'biggest_jumps')}
          scope={scope}
        />
        <ShooterRecordChart
          title="Most Sundays shot"
          valueLabel="Sundays"
          rows={data.most_events}
          urlKey="rec-events"
          field="most_events"
          range={rangeForExplainers}
          period={tag}
          size={size(data, 'most_events')}
          scope={scope}
        />
        <ShooterRecordChart
          title="Longest streaks"
          valueLabel="Consecutive Sundays"
          rows={data.longest_streaks}
          urlKey="rec-streaks"
          field="longest_streaks"
          range={rangeForExplainers}
          period={tag}
          size={size(data, 'longest_streaks')}
          scope={scope}
        />
        <HighestRatings
          rows={data.highest_ratings}
          period={tag}
          size={size(data, 'highest_ratings')}
          scope={scope}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full min-w-0 max-w-5xl flex-col gap-4 p-4">
      <div>
        <h1 className="text-2xl font-bold">Records</h1>
        <p className="text-sm text-text-muted">{tag}</p>
      </div>
      <PageTopSlot page="records" />
      {content}
    </div>
  );
}
