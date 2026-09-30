import { useCallback, useId, useState } from 'react';
import { Button } from '../../../components/ui/Button';
import { Skeleton } from '../../../components/ui/Skeleton';
import { AdminError } from '../../admin/components/AdminError';
import { JobProgress } from '../../admin/components/JobProgress';
import { formatDay } from '../../admin/format';
import { useMergeShooters, usePossibleDuplicates, useRefreshIdentity } from '../api';
import type { ShooterRef } from '../api';

type PendingMerge = { source: ShooterRef; target: ShooterRef; sharedDates: number };

function describeShooter(s: ShooterRef): string {
  const span =
    s.first_event === null || s.last_event === null
      ? 'no rounds'
      : `${formatDay(s.first_event)} – ${formatDay(s.last_event)}`;
  return `${s.display_name} (${s.n_rounds} rounds, ${span})`;
}

function isPair(p: PendingMerge, a: ShooterRef, b: ShooterRef): boolean {
  const ids = [p.source.shooter_id, p.target.shooter_id];
  return ids.includes(a.shooter_id) && ids.includes(b.shooter_id);
}

/** C8: every merge starts with a dry run; shared dates get a warning before the real merge (Plan 08 T5b). */
export function DuplicatesQueue() {
  const pairs = usePossibleDuplicates();
  const merge = useMergeShooters();
  const refresh = useRefreshIdentity();
  const confirmId = useId();
  const [pending, setPending] = useState<PendingMerge | null>(null);
  const [job, setJob] = useState<{ source: number; target: number; jobId: number } | null>(null);
  // Stable, so it runs only when the panel mounts: focus (and scroll) moves to it once, not on every render.
  const focusHeading = useCallback((el: HTMLElement | null) => el?.focus(), []);

  function preview(source: ShooterRef, target: ShooterRef) {
    setJob(null);
    merge.reset();
    merge.mutate(
      { source_shooter_id: source.shooter_id, target_shooter_id: target.shooter_id, dry_run: true },
      { onSuccess: (r) => setPending({ source, target, sharedDates: r.shared_dates }) },
    );
  }

  function confirm(p: PendingMerge) {
    merge.mutate(
      {
        source_shooter_id: p.source.shooter_id,
        target_shooter_id: p.target.shooter_id,
        dry_run: false,
      },
      {
        onSuccess: (r) => {
          setPending(null);
          if (r.job_id !== null)
            setJob({ source: p.source.shooter_id, target: p.target.shooter_id, jobId: r.job_id });
        },
      },
    );
  }

  if (pairs.isPending) return <Skeleton className="h-40" />;
  if (pairs.isError) return <AdminError error={pairs.error} />;

  const confirmPanel = (p: PendingMerge) => (
    <section
      key={`${p.source.shooter_id}-${p.target.shooter_id}`}
      aria-labelledby={confirmId}
      className="flex flex-col gap-2 rounded-card border border-accent p-3"
    >
      <h3 id={confirmId} ref={focusHeading} tabIndex={-1} className="font-medium">
        Confirm merge
      </h3>
      <p>{`Merge ${p.source.display_name} (#${p.source.shooter_id}) into ${p.target.display_name} (#${p.target.shooter_id})?`}</p>
      {p.sharedDates > 0 ? (
        <p className="text-error">
          {`Warning: they both have rounds on ${p.sharedDates} of the same dates, so they may be different people. Merging makes those days one shooter's.`}
        </p>
      ) : (
        <p>No shared dates.</p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button disabled={merge.isPending} onClick={() => confirm(p)}>
          {p.sharedDates > 0 ? 'Merge anyway' : 'Merge'}
        </Button>
        <Button
          variant="ghost"
          onClick={() => {
            setPending(null);
            merge.reset();
          }}
        >
          Cancel
        </Button>
      </div>
    </section>
  );

  return (
    <div className="flex flex-col gap-3">
      {merge.isError && <AdminError error={merge.error} />}
      {job !== null && (
        <JobProgress
          jobId={job.jobId}
          label={`Merging #${job.source} into #${job.target}`}
          onSettled={refresh}
        />
      )}
      {pairs.data.length === 0 ? (
        <p className="text-text-muted">No possible duplicates.</p>
      ) : (
        <ul
          aria-label="Possible duplicates"
          className="flex flex-col divide-y divide-outline-variant"
        >
          {pairs.data.map(({ a, b }) => (
            <li
              key={`${a.shooter_id}-${b.shooter_id}`}
              className="flex min-w-0 flex-col gap-2 py-2"
            >
              <span className="[overflow-wrap:anywhere]">{`${describeShooter(a)} ↔ ${describeShooter(b)}`}</span>
              <span className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                <Button
                  variant="tonal"
                  className="h-auto min-w-0 py-2 [overflow-wrap:anywhere]"
                  disabled={merge.isPending}
                  onClick={() => preview(a, b)}
                >{`Merge ${a.display_name} into ${b.display_name}`}</Button>
                <Button
                  variant="tonal"
                  className="h-auto min-w-0 py-2 [overflow-wrap:anywhere]"
                  disabled={merge.isPending}
                  onClick={() => preview(b, a)}
                >{`Merge ${b.display_name} into ${a.display_name}`}</Button>
              </span>
              {pending !== null && isPair(pending, a, b) && confirmPanel(pending)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
