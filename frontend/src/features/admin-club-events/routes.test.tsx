import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderRoutes } from '../../test/render';
import { nav, routes } from './routes';

describe('admin club-events route', () => {
  it('is an admin nav item at 915 with no filters', () => {
    expect(nav).toEqual([
      expect.objectContaining({
        label: 'Manage club events',
        path: '/admin/club-events',
        order: 915,
        adminOnly: true,
      }),
    ]);
    expect(routes[0]?.handle).toEqual({ filters: { roundType: false, window: false } });
  });

  it('shows the two tabs to an admin', async () => {
    renderRoutes(routes, { route: '/admin/club-events', role: 'admin' });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Club events' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Events' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Contacts' })).toBeInTheDocument();
  });

  it('is not shown to a viewer', async () => {
    renderRoutes(routes, { route: '/admin/club-events', role: 'viewer' });
    expect(await screen.findByText('Admins only')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Events' })).not.toBeInTheDocument();
  });
});
