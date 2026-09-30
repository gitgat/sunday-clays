import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { Job } from '../api';
import { JOB_MAX_ERRORS, jobPollDelay } from '../api';
import { doneJob } from '../mocks';
import { JobProgress, jobStatusText } from './JobProgress';

describe('jobStatusText', () => {
  it.each([
    [{ status: 'queued', error: null }, 'Queued…'],
    [{ status: 'running', error: null }, 'Running…'],
    [{ status: 'done', error: null }, 'Done'],
    [{ status: 'failed', error: 'boom' }, 'Failed: boom'],
    [{ status: 'failed', error: null }, 'Failed: unknown error'],
    [{ status: 'paused', error: null }, 'paused'],
  ])('%j → %s', (job, want) => {
    expect(jobStatusText(job as Pick<Job, 'status' | 'error'>)).toBe(want);
  });
});

function Harness({ onDone }: { onDone: () => void }) {
  const [renders, setRenders] = useState(0);
  return (
    <>
      <button type="button" onClick={() => setRenders(renders + 1)}>
        rerender
      </button>
      <JobProgress jobId={41} label="Rebuilding live data" onSettled={() => onDone()} />
    </>
  );
}

describe('jobPollDelay', () => {
  it('polls every second, backs off after errors and stops when settled or after too many errors', () => {
    expect(jobPollDelay(undefined, 0)).toBe(1000);
    expect(jobPollDelay('running', 0)).toBe(1000);
    expect(jobPollDelay(undefined, 1)).toBe(2000);
    expect(jobPollDelay(undefined, 3)).toBe(8000);
    expect(jobPollDelay('done', 0)).toBe(false);
    expect(jobPollDelay('failed', 0)).toBe(false);
    expect(jobPollDelay(undefined, JOB_MAX_ERRORS)).toBe(false);
  });
});

describe('JobProgress', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls until the job is done and calls onDone exactly once', async () => {
    let calls = 0;
    server.use(
      http.get('*/api/admin/jobs/:id', () => {
        calls += 1;
        return HttpResponse.json({ ...doneJob, status: calls === 1 ? 'running' : 'done' });
      }),
    );
    const onDone = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(<Harness onDone={onDone} />);
    expect(await screen.findByText('Rebuilding live data: Running…')).toBeInTheDocument();
    expect(
      await screen.findByText('Rebuilding live data: Done', undefined, { timeout: 3000 }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'rerender' }));
    await user.click(screen.getByRole('button', { name: 'rerender' }));
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('status')).toHaveTextContent('Rebuilding live data: Done');
  });

  it('calls onDone for a failed job too', async () => {
    server.use(
      http.get('*/api/admin/jobs/:id', () =>
        HttpResponse.json({ ...doneJob, status: 'failed', error: 'boom' }),
      ),
    );
    const onDone = vi.fn();
    renderWithProviders(<Harness onDone={onDone} />);
    expect(await screen.findByText('Rebuilding live data: Failed: boom')).toBeInTheDocument();
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it('backs off on lookup errors, then stops polling and says so', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let calls = 0;
    server.use(
      http.get('*/api/admin/jobs/:id', () => {
        calls += 1;
        return HttpResponse.json(
          { error: { code: 'not_found', message: 'No such job' } },
          { status: 404 },
        );
      }),
    );
    renderWithProviders(<JobProgress jobId={77} label="Rebuild" />);
    expect(await screen.findByText("Rebuild: couldn't check job #77")).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
    for (let i = 0; i < 6; i += 1) await vi.advanceTimersByTimeAsync(20_000);
    expect(calls).toBe(JOB_MAX_ERRORS);
    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Rebuild: couldn't check job #77 and stopped trying; reload the page to check again",
    );
    await vi.advanceTimersByTimeAsync(120_000);
    expect(calls).toBe(JOB_MAX_ERRORS);
  });

  it('shows the failure reason and works without onDone', async () => {
    server.use(
      http.get('*/api/admin/jobs/:id', () =>
        HttpResponse.json({ ...doneJob, status: 'failed', error: 'no_handler' }),
      ),
    );
    renderWithProviders(<JobProgress jobId={41} label="Recompute" />);
    expect(await screen.findByText('Recompute: Failed: no_handler')).toBeInTheDocument();
  });

  it('says so when the job cannot be checked', async () => {
    server.use(
      http.get('*/api/admin/jobs/:id', () =>
        HttpResponse.json(
          { error: { code: 'not_found', message: 'No such job' } },
          { status: 404 },
        ),
      ),
    );
    renderWithProviders(<JobProgress jobId={77} label="Rebuild" />);
    expect(await screen.findByText("Rebuild: couldn't check job #77")).toBeInTheDocument();
  });
});
