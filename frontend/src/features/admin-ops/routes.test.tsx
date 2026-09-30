import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { renderRoutes } from '../../test/render';
import { doneJob, shooterMatches } from '../admin/mocks';
import { routes } from './routes';

// The route renders inside RequireRole role="admin" (Plan 07 D10, Decision D13), so the session role is seeded.
function renderAt(role: 'viewer' | 'admin') {
  renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], {
    route: '/admin/ops',
    role,
  });
}

// Runs on this feature's default handlers (./mocks) on purpose; /api/shooters and jobs belong to other features.
describe('admin-ops routes', () => {
  it('serve the ops page at /admin/ops and run both actions', async () => {
    server.use(
      http.get('*/api/shooters', () => HttpResponse.json(shooterMatches)),
      http.get('*/api/admin/jobs/:id', ({ params }) =>
        HttpResponse.json({ ...doneJob, id: Number(params.id) }),
      ),
    );
    renderAt('admin');
    const user = userEvent.setup();
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Data & ops' }),
    ).toBeInTheDocument();
    expect(await screen.findByRole('table', { name: 'Audit log' })).toBeInTheDocument();

    await user.click(await screen.findByRole('button', { name: 'Assign to shooter' }));
    await user.type(screen.getByRole('searchbox', { name: 'Shooter for “Hadley, Dik”' }), 'cr');
    await user.click(await screen.findByRole('button', { name: 'Hadley, Ike · 267 rounds' }));
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    expect(await screen.findByText('Alias hadley dik → #3: Done')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Recompute analytics' }));
    expect(await screen.findByText('Recompute: Done')).toBeInTheDocument();
  });

  it('a viewer session gets the admins-only page instead of the ops page', async () => {
    renderAt('viewer');
    expect(await screen.findByRole('heading', { name: 'Admins only' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 1, name: 'Data & ops' })).not.toBeInTheDocument();
  });
});
