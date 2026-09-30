import { useEffect, useRef } from 'react';
import { JOB_MAX_ERRORS, useJob } from '../api';
import type { Job } from '../api';

export function jobStatusText(job: Pick<Job, 'status' | 'error'>): string {
  switch (job.status) {
    case 'queued':
      return 'Queued…';
    case 'running':
      return 'Running…';
    case 'done':
      return 'Done';
    case 'failed':
      return `Failed: ${job.error ?? 'unknown error'}`;
    default:
      return String(job.status);
  }
}

/**
 * Live status of one worker job (polled every JOB_POLL_MS until done or failed, backing off and then giving up when
 * the lookup keeps failing); `onSettled` fires once per job id when the job is done or failed.
 */
export function JobProgress({
  jobId,
  label,
  onSettled,
}: {
  jobId: number;
  label: string;
  onSettled?: () => void;
}) {
  const job = useJob(jobId);
  const status = job.data?.status;
  const firedFor = useRef<number | null>(null);

  useEffect(() => {
    if ((status === 'done' || status === 'failed') && firedFor.current !== jobId) {
      firedFor.current = jobId;
      onSettled?.();
    }
  }, [status, jobId, onSettled]);

  const stopped = job.isError && job.errorUpdateCount >= JOB_MAX_ERRORS;
  let text: string;
  if (stopped)
    text = `couldn't check job #${jobId} and stopped trying; reload the page to check again`;
  else if (job.isError) text = `couldn't check job #${jobId}`;
  else if (job.data === undefined) text = 'Queued…';
  else text = jobStatusText(job.data);

  return (
    <p
      role={stopped ? 'alert' : 'status'}
      aria-live="polite"
      className="rounded-card border border-outline-variant p-3"
    >
      {`${label}: ${text}`}
    </p>
  );
}
