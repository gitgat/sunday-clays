import { Chip } from '../../../components/ui/Chip';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useMeta, usePageDefaultWindow, useTimeWindow } from '../../../lib/timeWindow';
import { useLegacyParams } from '../../../lib/useLegacyParams';
import { useUrlState } from '../../../lib/useUrlState';
import { convertLegacyRace } from '../../competition/legacyParams';
import { WidenWindow } from '../../competition/WidenWindow';
import { datesText, sundaysNote, THIN_SUNDAYS, windowInWords } from '../../competition/windowText';
import { type LeaderboardMetric, useLeaderboardHistory } from '../api';
import { RaceIntro } from '../components/RaceIntro';
import { RaceView } from '../components/RaceView';
import { METRICS, RACE_MODES, RACE_TOP, type RaceMode, oneOf } from '../labels';

const MODE_CODEC = oneOf(
  RACE_MODES.map((m) => m.value),
  'rolling_12',
);
const METRIC_CODEC = oneOf(
  METRICS.map((m) => m.value),
  'season_points',
);

export function RacePage() {
  const meta = useMeta().data;
  const pageDefault = usePageDefaultWindow();
  const legacy = useLegacyParams((params) =>
    convertLegacyRace(params, {
      firstSunday: meta?.first_event_date ?? null,
      lastSunday: meta?.last_score_date ?? null,
      pageDefault,
    }),
  );
  const { window: timeWindow, range } = useTimeWindow();
  const [mode, setMode] = useUrlState<RaceMode>('period', MODE_CODEC, 'rolling_12');
  const [metric, setMetric] = useUrlState<LeaderboardMetric>(
    'metric',
    METRIC_CODEC,
    'season_points',
  );

  // The header window sets the replayed Sundays; without a lower bound (All) it starts on the first one.
  const from = range === null ? null : (range.from ?? meta?.first_event_date ?? null);
  const to = range?.to ?? null;
  const history = useLeaderboardHistory({
    period: mode,
    metric,
    from: from ?? '',
    to: to ?? '',
    top: RACE_TOP,
    enabled: !legacy && from !== null && to !== null,
  });
  const frames = history.data?.frames;
  const where = windowInWords(timeWindow);

  let content;
  if (legacy) {
    content = <Skeleton className="h-96" />;
  } else if (history.isError) {
    content = <EmptyState title="Race unavailable" description="Try again in a moment." />;
  } else if (frames === undefined || from === null || to === null) {
    content = <Skeleton className="h-96" />;
  } else if (frames.length === 0) {
    content = (
      <EmptyState
        title={`No Sundays with scores in ${where}`}
        description="Widen the window to replay more Sundays."
        action={<WidenWindow />}
      />
    );
  } else {
    content = (
      <>
        <p className="text-sm font-medium">
          Replaying {datesText(from, to, meta?.last_score_date ?? null)} · {String(frames.length)}{' '}
          Sunday{frames.length === 1 ? '' : 's'}
        </p>
        {frames.length < THIN_SUNDAYS && (
          <div className="flex flex-col gap-2 rounded-card bg-elevated p-3 text-sm">
            <p>{sundaysNote(frames.length, timeWindow)}</p>
            <WidenWindow />
          </div>
        )}
        <RaceView
          key={`${mode}|${metric}|${from}|${to}`}
          frames={frames}
          metric={metric}
          mode={mode}
          query={{ period: mode, metric, from, to }}
        />
      </>
    );
  }

  return (
    <div className="mx-auto grid w-full min-w-0 max-w-5xl grid-cols-1 gap-4 p-4">
      <h1 className="text-2xl font-bold">Race</h1>
      <RaceIntro mode={mode} />
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1 text-sm">
          <span id="race-points-label">Points over</span>
          <div role="group" aria-labelledby="race-points-label" className="flex flex-wrap gap-2">
            {RACE_MODES.map((m) => (
              <Chip
                key={m.value}
                selected={m.value === mode}
                onClick={() => {
                  setMode(m.value);
                }}
              >
                {m.label}
              </Chip>
            ))}
          </div>
        </div>
        <label className="flex flex-col gap-1 text-sm">
          Metric
          <select
            value={metric}
            onChange={(event) => {
              setMetric(METRIC_CODEC.parse(event.currentTarget.value));
            }}
            className="min-h-11 rounded-button bg-elevated px-3"
          >
            {METRICS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="min-w-0 grid grid-cols-1 gap-4">{content}</div>
    </div>
  );
}
