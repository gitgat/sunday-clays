import { fireEvent, screen, within } from '@testing-library/react';
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
    route: '/admin/identity',
    role,
  });
}

// Runs on this feature's default handlers (./mocks) on purpose; /api/shooters and jobs belong to other features.
describe('admin-identity routes', () => {
  it('serve the identity page at /admin/identity and exercise each action', async () => {
    server.use(
      http.get('*/api/shooters', () => HttpResponse.json(shooterMatches)),
      http.get('*/api/admin/jobs/:id', ({ params }) =>
        HttpResponse.json({ ...doneJob, id: Number(params.id) }),
      ),
    );
    renderAt('admin');
    const user = userEvent.setup();
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Identity & rules' }),
    ).toBeInTheDocument();

    await user.click(
      await screen.findByRole('button', { name: 'Merge Hamond, Bennett into Hammond, Bennett' }),
    );
    const confirm = await screen.findByRole('region', { name: 'Confirm merge' });
    await user.click(within(confirm).getByRole('button', { name: 'Merge' }));

    await user.click(await screen.findByRole('button', { name: 'Deactivate rule #1' }));
    expect(await screen.findByText('Deactivating rule #1: Done')).toBeInTheDocument();

    const [renamePicker, statusPicker] = screen.getAllByRole('searchbox', { name: 'Shooter' });
    await user.type(renamePicker as HTMLElement, 'cr');
    await user.click(
      (
        await screen.findAllByRole('button', { name: 'Hadley, Ike · 267 rounds' })
      )[0] as HTMLElement,
    );
    await user.type(screen.getByLabelText('New display name'), 'Hadley, Clint');
    await user.click(screen.getByRole('button', { name: 'Rename' }));
    expect(await screen.findByText('Renaming #3: Done')).toBeInTheDocument();

    await user.type(statusPicker as HTMLElement, 'cr');
    await user.click(
      (
        await screen.findAllByRole('button', { name: 'Hadley, Ike · 267 rounds' })
      )[0] as HTMLElement,
    );
    await user.selectOptions(screen.getByLabelText('Status'), 'guest');
    await user.click(screen.getByRole('button', { name: 'Set status' }));
    expect(await screen.findByText('Setting status of #3: Done')).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText('Rule type'), 'station_reset');
    await user.type(screen.getByLabelText('Station (like 7 or 7A)'), '6');
    await user.type(screen.getByLabelText('What changed'), 'New presentation');
    fireEvent.change(screen.getByLabelText('Effective date'), { target: { value: '2026-10-04' } });
    await user.click(screen.getByRole('button', { name: 'Create rule' }));
    expect(await screen.findByText('Rule #3: Done')).toBeInTheDocument();
  }, 30_000);

  it('a viewer session gets the admins-only page instead of the identity page', async () => {
    renderAt('viewer');
    expect(
      await screen.findByRole('heading', { name: 'Admins only' }, { timeout: 10_000 }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('heading', { level: 1, name: 'Identity & rules' }),
    ).not.toBeInTheDocument();
  }, 30_000);
});
