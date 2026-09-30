import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import type { ImportSummary } from '../api';
import { doneJob, importsList } from '../mocks';
import { ImportHistory } from './ImportHistory';

let list: ImportSummary[] = [];
const rollbacks: string[] = [];
const discards: string[] = [];

function row(filename: string) {
  return screen.getByRole('row', { name: new RegExp(filename.replace('.', '\\.')) });
}

describe('ImportHistory', () => {
  beforeEach(() => {
    list = importsList.map((i) => ({ ...i }));
    rollbacks.length = 0;
    discards.length = 0;
    server.use(
      http.get('*/api/admin/imports', () => HttpResponse.json(list)),
      http.post('*/api/admin/imports/:id/rollback', ({ params }) => {
        rollbacks.push(String(params.id));
        list = list.map((i) =>
          String(i.id) === params.id
            ? { ...i, status: 'rolled_back', rolled_back_at: '2026-09-27T20:00:00Z' }
            : i,
        );
        return HttpResponse.json({ job_id: 42 });
      }),
      http.post('*/api/admin/imports/:id/discard', ({ params }) => {
        discards.push(String(params.id));
        list = list.map((i) => (String(i.id) === params.id ? { ...i, status: 'discarded' } : i));
        return new HttpResponse(null, { status: 204 });
      }),
      http.get('*/api/admin/jobs/:id', ({ params }) =>
        HttpResponse.json({ ...doneJob, id: Number(params.id) }),
      ),
    );
  });

  it('lists imports newest first with status, kind and upload time', async () => {
    renderWithProviders(<ImportHistory />);
    const table = await screen.findByRole('table', { name: 'Import history' });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((r) => within(r).getAllByRole('cell')[0]?.textContent)).toEqual([
      '#3',
      '#2',
      '#1',
    ]);
    expect(row('scores_old.xlsx')).toHaveTextContent('Pending');
    expect(row('stations_2026-09-27.xlsx')).toHaveTextContent('Station workbook');
    expect(
      within(row('scores_old.xlsx')).getByRole('link', { name: 'scores_old.xlsx' }),
    ).toHaveAttribute('href', '/admin/imports/3');
  });

  it('links keep the round-type filter', async () => {
    renderWithProviders(<ImportHistory />, { route: '/admin?rt=sporting' });
    await screen.findByRole('table', { name: 'Import history' });
    expect(
      within(row('scores_old.xlsx')).getByRole('link', { name: 'scores_old.xlsx' }),
    ).toHaveAttribute('href', '/admin/imports/3?rt=sporting');
  });

  it('rolls back a committed import after a second confirming click', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ImportHistory />);
    await user.click(
      await within(await screen.findByRole('row', { name: /stations_2026-09-27/ })).findByRole(
        'button',
        { name: 'Roll back' },
      ),
    );
    expect(rollbacks).toEqual([]);
    await user.click(
      within(row('stations_2026-09-27.xlsx')).getByRole('button', { name: 'Confirm roll back' }),
    );
    expect(await screen.findByText('Rolling back #2: Done')).toBeInTheDocument();
    expect(rollbacks).toEqual(['2']);
    expect(await screen.findByText('Rolled back')).toBeInTheDocument();
  });

  it('drops the roll back button as soon as the roll back is accepted, while the job still runs', async () => {
    server.use(
      http.get('*/api/admin/jobs/:id', () => HttpResponse.json({ ...doneJob, status: 'running' })),
    );
    const user = userEvent.setup();
    renderWithProviders(<ImportHistory />);
    await user.click(
      await within(await screen.findByRole('row', { name: /stations_2026-09-27/ })).findByRole(
        'button',
        { name: 'Roll back' },
      ),
    );
    await user.click(
      within(row('stations_2026-09-27.xlsx')).getByRole('button', { name: 'Confirm roll back' }),
    );
    expect(await screen.findByText('Rolling back #2: Running…')).toBeInTheDocument();
    await within(row('stations_2026-09-27.xlsx')).findByText('Rolled back');
    expect(
      within(row('stations_2026-09-27.xlsx')).queryByRole('button', { name: 'Roll back' }),
    ).not.toBeInTheDocument();
  });

  it('offers no roll back for a row whose rollback job runs, even before the list catches up', async () => {
    server.use(
      http.post('*/api/admin/imports/:id/rollback', () => HttpResponse.json({ job_id: 42 })),
      http.get('*/api/admin/imports', () => HttpResponse.json(list)),
      http.get('*/api/admin/jobs/:id', () => HttpResponse.json({ ...doneJob, status: 'running' })),
    );
    const user = userEvent.setup();
    renderWithProviders(<ImportHistory />);
    await user.click(
      await within(await screen.findByRole('row', { name: /stations_2026-09-27/ })).findByRole(
        'button',
        { name: 'Roll back' },
      ),
    );
    await user.click(
      within(row('stations_2026-09-27.xlsx')).getByRole('button', { name: 'Confirm roll back' }),
    );
    expect(await screen.findByText('Rolling back #2: Running…')).toBeInTheDocument();
    expect(row('stations_2026-09-27.xlsx')).toHaveTextContent('Committed');
    expect(
      within(row('stations_2026-09-27.xlsx')).queryByRole('button', { name: /roll back/i }),
    ).not.toBeInTheDocument();
    expect(
      within(row('scores_2026-09-27.xlsx')).getByRole('button', { name: 'Roll back' }),
    ).toBeEnabled();
  });

  it('cancelling a roll back sends nothing', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ImportHistory />);
    await user.click(
      await within(await screen.findByRole('row', { name: /scores_2026-09-27/ })).findByRole(
        'button',
        { name: 'Roll back' },
      ),
    );
    await user.click(within(row('scores_2026-09-27.xlsx')).getByRole('button', { name: 'Cancel' }));
    expect(
      within(row('scores_2026-09-27.xlsx')).getByRole('button', { name: 'Roll back' }),
    ).toBeInTheDocument();
    expect(rollbacks).toEqual([]);
  });

  it('discards a pending import', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ImportHistory />);
    await user.click(
      await within(await screen.findByRole('row', { name: /scores_old/ })).findByRole('button', {
        name: 'Discard',
      }),
    );
    expect(await screen.findByText('Discarded')).toBeInTheDocument();
    expect(discards).toEqual(['3']);
  });

  it('shows a rejected roll back next to the table', async () => {
    server.use(
      http.post('*/api/admin/imports/:id/rollback', () =>
        HttpResponse.json(
          { error: { code: 'conflict', message: 'Only committed imports can be rolled back' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ImportHistory />);
    await user.click(
      await within(await screen.findByRole('row', { name: /stations_2026-09-27/ })).findByRole(
        'button',
        { name: 'Roll back' },
      ),
    );
    await user.click(
      within(row('stations_2026-09-27.xlsx')).getByRole('button', { name: 'Confirm roll back' }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Only committed imports can be rolled back',
    );
  });

  it('blocks a second roll back or discard while one is in flight', async () => {
    let answer: () => void = () => undefined;
    const answered = new Promise<void>((resolve) => {
      answer = resolve;
    });
    server.use(
      http.post('*/api/admin/imports/:id/rollback', async ({ params }) => {
        rollbacks.push(String(params.id));
        await answered;
        return HttpResponse.json({ job_id: 42 });
      }),
      http.post('*/api/admin/imports/:id/discard', async ({ params }) => {
        discards.push(String(params.id));
        await answered;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ImportHistory />);
    await user.click(
      await within(await screen.findByRole('row', { name: /stations_2026-09-27/ })).findByRole(
        'button',
        { name: 'Roll back' },
      ),
    );
    const confirm = within(row('stations_2026-09-27.xlsx')).getByRole('button', {
      name: 'Confirm roll back',
    });
    await user.click(confirm);
    expect(confirm).toBeDisabled();
    const discard = within(row('scores_old.xlsx')).getByRole('button', { name: 'Discard' });
    await user.click(discard);
    expect(discard).toBeDisabled();
    answer();
    expect(await screen.findByText('Rolling back #2: Done')).toBeInTheDocument();
    expect(rollbacks).toEqual(['2']);
    expect(discards).toEqual(['3']);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows a rejected discard next to the table', async () => {
    server.use(
      http.post('*/api/admin/imports/:id/discard', () =>
        HttpResponse.json(
          { error: { code: 'not_pending', message: 'Import 3 is not pending' } },
          { status: 409 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<ImportHistory />);
    await user.click(
      await within(await screen.findByRole('row', { name: /scores_old/ })).findByRole('button', {
        name: 'Discard',
      }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('Import 3 is not pending');
  });

  it('invites the first upload when there is no history', async () => {
    server.use(http.get('*/api/admin/imports', () => HttpResponse.json([])));
    renderWithProviders(<ImportHistory />);
    expect(
      await screen.findByText('No imports yet — upload a workbook to start.'),
    ).toBeInTheDocument();
  });
});
