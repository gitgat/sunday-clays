import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { useState } from 'react';
import { Route, Routes } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { ImportPreview } from '../api';
import { doneJob, duplicatePreview, scoresPreview, stalePreview } from '../mocks';
import { ImportPreviewView } from './ImportPreviewView';

/** Stands in for ImportDetailPage, whose status comes from the import list that a finished commit refreshes. */
function StatusHarness() {
  const [status, setStatus] = useState('pending');
  return (
    <>
      <button type="button" onClick={() => setStatus('committed')}>
        List says committed
      </button>
      <ImportPreviewView preview={scoresPreview} status={status} />
    </>
  );
}

function renderPreview(preview: ImportPreview, status: string | undefined, search = '') {
  return renderWithProviders(
    <Routes>
      <Route
        path="/admin/imports/:id"
        element={<ImportPreviewView preview={preview} status={status} />}
      />
      <Route path="/admin" element={<p>imports page</p>} />
    </Routes>,
    { route: `/admin/imports/${preview.import_id}${search}` },
  );
}

describe('ImportPreviewView', () => {
  it('a pending import shows its changes, findings, commit and discard', () => {
    renderPreview(stalePreview, 'pending');
    expect(screen.getByRole('heading', { level: 1, name: 'Import #3' })).toBeInTheDocument();
    expect(screen.getByText('scores_old.xlsx · Scores workbook · Pending')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Removals' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Will not be imported' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Commit import' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Discard this upload' })).toBeEnabled();
  });

  it('a duplicate upload says it was already imported and offers no commit', () => {
    // Plan 03: the duplicate is import #2 itself (import_id === duplicate_of), which is committed.
    renderPreview(duplicatePreview, 'committed');
    expect(screen.getByRole('heading', { level: 1, name: 'Import #2' })).toBeInTheDocument();
    expect(
      screen.getByText('Already imported as import #2. Nothing to commit.'),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Commit import' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Discard this upload' })).not.toBeInTheDocument();
  });

  it('a re-upload of a still-pending file points at that import and keeps its actions', () => {
    renderPreview({ ...stalePreview, duplicate_of: stalePreview.import_id }, 'pending');
    expect(
      screen.getByText(
        'Already uploaded as import #3, which is still pending: review it below, then commit or discard it.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Commit import' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Discard this upload' })).toBeEnabled();
  });

  it('keeps the commit progress on screen once the list reports the import committed', async () => {
    server.use(
      http.post('*/api/admin/imports/:id/commit', () => HttpResponse.json({ job_id: 41 })),
      http.get('*/api/admin/jobs/:id', () => HttpResponse.json(doneJob)),
    );
    const user = userEvent.setup();
    renderWithProviders(<StatusHarness />, { route: '/admin/imports/4' });
    await user.click(screen.getByRole('button', { name: 'Commit import' }));
    expect(await screen.findByText('Rebuilding live data: Done')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'List says committed' }));
    expect(screen.getByText('Rebuilding live data: Done')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Commit import' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Discard this upload' })).not.toBeInTheDocument();
  });

  it('refreshes the import as soon as the commit is accepted and again when the rebuild fails', async () => {
    let jobStatus = 'running';
    server.use(
      http.post('*/api/admin/imports/:id/commit', () => HttpResponse.json({ job_id: 41 })),
      http.get('*/api/admin/jobs/:id', () =>
        HttpResponse.json({ ...doneJob, status: jobStatus, error: 'boom' }),
      ),
    );
    const { user, queryClient } = renderWithProviders(<StatusHarness />, {
      route: '/admin/imports/4',
    });
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    await user.click(screen.getByRole('button', { name: 'Commit import' }));
    expect(await screen.findByText('Rebuilding live data: Running…')).toBeInTheDocument();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['/api/admin/imports'] });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['/api/admin/imports/{id}', 4] });
    // The panel stays even though the job has not finished and the status prop still says pending.
    expect(screen.getByRole('button', { name: 'Commit import' })).toBeDisabled();
    invalidate.mockClear();
    jobStatus = 'failed';
    expect(
      await screen.findByText('Rebuilding live data: Failed: boom', undefined, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['/api/admin/imports'] });
  });

  it('a committed import shows no actions', () => {
    renderPreview(stalePreview, 'committed');
    expect(screen.queryByRole('button', { name: 'Commit import' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Discard this upload' })).not.toBeInTheDocument();
  });

  it('an unknown status shows an ellipsis and no actions', () => {
    renderPreview(stalePreview, undefined);
    expect(screen.getByText('scores_old.xlsx · Scores workbook · …')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Discard this upload' })).not.toBeInTheDocument();
  });

  it('discarding returns to the import list', async () => {
    server.use(
      http.post('*/api/admin/imports/:id/discard', () => new HttpResponse(null, { status: 204 })),
    );
    const user = userEvent.setup();
    const { router } = renderPreview(stalePreview, 'pending', '?rt=sporting');
    await user.click(screen.getByRole('button', { name: 'Discard this upload' }));
    expect(await screen.findByText('imports page')).toBeInTheDocument();
    // The global round-type filter survives in-app navigation (C10).
    expect(router.state.location.search).toBe('?rt=sporting');
  });

  it('a failed discard shows the server message', async () => {
    server.use(
      http.post('*/api/admin/imports/:id/discard', () =>
        HttpResponse.json(
          { error: { code: 'not_pending', message: 'Import 3 is not pending' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderPreview(stalePreview, 'pending');
    await user.click(screen.getByRole('button', { name: 'Discard this upload' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Import 3 is not pending');
  });
});
