import { Ribbon } from 'lucide-react';
import { Skeleton } from '../../../components/ui/Skeleton';
import { Stat } from '../../../components/ui/Stat';
import { isCustomWindow, useMeta, useTimeWindow } from '../../../lib/timeWindow';
import { plural } from '../format';
import { windowPhrase, windowTagText } from '../../../lib/windowText';
import type { ShooterDetail } from '../api';
import { explainers } from '../explainers';
import { formatScore, spanText } from '../format';
import { MeButton } from './MeButton';

const STATUS_LABELS: Record<string, string | undefined> = { member: 'Member', guest: 'Guest' };

export function ProfileHero({
  shooter,
  isPlaceholderData = false,
}: {
  shooter: ShooterDetail;
  /** True while the numbers on screen belong to the previous window. */
  isPlaceholderData?: boolean;
}) {
  // 'deceased' has no label: the memorial marker (Plan 06 `deceased`) covers it.
  const statusLabel = STATUS_LABELS[shooter.status];
  const { stats, window_stats: inWindow } = shooter;
  const { window, range } = useTimeWindow();
  const meta = useMeta();
  return (
    <header className="flex flex-col gap-3 rounded-card bg-elevated p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-medium">{shooter.display_name}</h1>
          {shooter.deceased && (
            <p className="flex items-center gap-2 text-accent">
              <Ribbon aria-hidden="true" className="size-4" />
              In memoriam
            </p>
          )}
          <p className="flex flex-wrap gap-2 text-sm text-text-muted">
            {statusLabel && <span>{statusLabel}</span>}
            <span>{spanText(shooter.first_event, shooter.last_event)}</span>
          </p>
        </div>
        {/* "That's me" is for living shooters; the memorial marker above stays. */}
        {!shooter.deceased && <MeButton shooterId={shooter.shooter_id} />}
      </div>
      {window !== 'all' && (
        <div
          className={`flex flex-col gap-2 ${isPlaceholderData ? 'opacity-60' : ''}`}
          aria-busy={isPlaceholderData}
        >
          {range === null && !isCustomWindow(window) ? (
            meta.isError ? (
              <p className="text-text-muted">Couldn't load the time window.</p>
            ) : (
              <Skeleton label="Loading the time window" className="h-16" />
            )
          ) : (
            <>
              <h2 className="text-sm font-medium">{`In ${windowPhrase(window, range)}`}</h2>
              <p className="sr-only">{windowTagText(window, range)}</p>
              {isPlaceholderData && (
                <span className="sr-only" aria-label="Loading this window" role="status" />
              )}
              {inWindow === undefined || inWindow === null || inWindow.n_rounds === 0 ? (
                <p className="text-text-muted">
                  {`No rounds in ${windowPhrase(window, range)}. Pick 12M or All in the time filter above to see more.`}
                </p>
              ) : (
                <div className="grid grid-cols-3 gap-2">
                  <Stat
                    label="Rounds"
                    value={String(inWindow.n_rounds)}
                    hint={plural(inWindow.n_events, 'Sunday')}
                    explainer={explainers['win-rounds']}
                  />
                  <Stat
                    label="Average"
                    value={formatScore(inWindow.avg_score)}
                    explainer={explainers['win-average']}
                  />
                  <Stat
                    label="Best"
                    value={formatScore(inWindow.best_score)}
                    explainer={explainers['win-best']}
                  />
                </div>
              )}
            </>
          )}
        </div>
      )}
      <div className="flex flex-col gap-2">
        <h2 className="text-sm font-medium">Lifetime</h2>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Stat
            label="Rounds"
            value={String(stats.n_rounds)}
            explainer={explainers['hero-rounds']}
          />
          <Stat
            label="Sundays"
            value={String(stats.n_events)}
            explainer={explainers['hero-sundays']}
          />
          <Stat
            label="Average"
            value={formatScore(stats.avg_score)}
            explainer={explainers['hero-average']}
          />
          <Stat
            label="Median"
            value={formatScore(stats.median_score)}
            explainer={explainers['hero-median']}
          />
          <Stat
            label="Best"
            value={formatScore(stats.best_score)}
            explainer={explainers['hero-best']}
          />
        </div>
      </div>
    </header>
  );
}
