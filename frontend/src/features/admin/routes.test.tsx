import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { renderRoutes } from '../../test/render';
import { nav, routes } from './routes';

// Runs on this feature's default handlers (./mocks) on purpose: every handler line executes here. Every admin route
// renders inside RequireRole role="admin" (Plan 07 D10, Decision D13), so the session is seeded as admin by default.
function renderAt(path: string, role: 'viewer' | 'admin' = 'admin') {
  return renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], {
    route: path,
    role,
  }).router;
}

describe('admin routes', () => {
  it('upload → preview at /admin/imports/:id', async () => {
    const user = userEvent.setup();
    const router = renderAt('/admin');
    await user.upload(
      await screen.findByLabelText('Workbook (.xlsx)'),
      new File(['PK'], 'scores.xlsx'),
    );
    await user.click(screen.getByRole('button', { name: 'Upload and preview' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Import #4' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/admin/imports/4');
  });

  it('commit a pending import and watch the rebuild finish', async () => {
    const user = userEvent.setup();
    renderAt('/admin/imports/3');
    await user.click(await screen.findByRole('checkbox', { name: /removes the events and rows/ }));
    await user.click(await screen.findByRole('button', { name: 'Commit import' }));
    expect(await screen.findByText('Rebuilding live data: Done')).toBeInTheDocument();
  });

  it('roll back and discard from the history', async () => {
    const user = userEvent.setup();
    renderAt('/admin');
    const table = await screen.findByRole('table', { name: 'Import history' });
    await user.click(
      within(within(table).getByRole('row', { name: /stations_2026/ })).getByRole('button', {
        name: 'Roll back',
      }),
    );
    await user.click(
      within(within(table).getByRole('row', { name: /stations_2026/ })).getByRole('button', {
        name: 'Confirm roll back',
      }),
    );
    expect(await screen.findByText('Rolling back #2: Done')).toBeInTheDocument();
    await user.click(
      within(within(table).getByRole('row', { name: /scores_old/ })).getByRole('button', {
        name: 'Discard',
      }),
    );
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('a viewer session gets the admins-only page instead of the admin screens', async () => {
    renderAt('/admin', 'viewer');
    expect(await screen.findByRole('heading', { name: 'Admins only' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Workbook (.xlsx)')).not.toBeInTheDocument();
  });

  it('adds one admin-only Imports nav item (Decision D13)', () => {
    expect(
      nav.map(({ label, path, order, adminOnly }) => ({ label, path, order, adminOnly })),
    ).toEqual([{ label: 'Imports', path: '/admin', order: 900, adminOnly: true }]);
  });
});
