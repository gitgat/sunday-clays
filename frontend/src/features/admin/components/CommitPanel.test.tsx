import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { doneJob, scoresPreview, stalePreview } from '../mocks';
import { CommitPanel } from './CommitPanel';

function captureCommits() {
  const bodies: unknown[] = [];
  server.use(
    http.post('*/api/admin/imports/:id/commit', async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json({ job_id: 41 });
    }),
    http.get('*/api/admin/jobs/:id', () => HttpResponse.json(doneJob)),
  );
  return bodies;
}

describe('CommitPanel', () => {
  it('commit stays disabled until removals are confirmed', async () => {
    const bodies = captureCommits();
    const user = userEvent.setup();
    renderWithProviders(
      <CommitPanel preview={stalePreview} onStarted={vi.fn()} onSettled={vi.fn()} />,
    );
    const commit = screen.getByRole('button', { name: 'Commit import' });
    expect(commit).toBeDisabled();
    await user.click(
      screen.getByRole('checkbox', { name: /removes the events and rows listed above/ }),
    );
    expect(commit).toBeEnabled();
    await user.click(commit);
    expect(await screen.findByText('Rebuilding live data: Done')).toBeInTheDocument();
    expect(bodies).toEqual([{ confirm_removals: true }]);
  });

  it('commits without a checkbox when nothing is removed and reports when the rebuild is done', async () => {
    const bodies = captureCommits();
    const onStarted = vi.fn();
    const onSettled = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <CommitPanel preview={scoresPreview} onStarted={onStarted} onSettled={onSettled} />,
    );
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Commit import' }));
    expect(await screen.findByText('Rebuilding live data: Done')).toBeInTheDocument();
    expect(bodies).toEqual([{ confirm_removals: false }]);
    expect(onStarted).toHaveBeenCalledTimes(1);
    expect(onSettled).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Commit import' })).toBeDisabled();
  });

  it('commit conflict shows the server message', async () => {
    server.use(
      http.post('*/api/admin/imports/:id/commit', () =>
        HttpResponse.json(
          { error: { code: 'not_pending', message: 'Import 4 is not pending' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(
      <CommitPanel preview={scoresPreview} onStarted={vi.fn()} onSettled={vi.fn()} />,
    );
    await user.click(screen.getByRole('button', { name: 'Commit import' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Import 4 is not pending');
    expect(screen.getByRole('button', { name: 'Commit import' })).toBeEnabled();
  });
});
