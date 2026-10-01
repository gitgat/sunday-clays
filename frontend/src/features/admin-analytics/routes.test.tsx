import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderRoutes } from '../../test/render';
import { nav, routes } from './routes';

function renderAt(role: 'viewer' | 'admin') {
  renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], {
    route: '/admin/analytics',
    role,
  });
}

describe('admin-analytics routes', () => {
  it('serve the Analytics page to an admin', async () => {
    renderAt('admin');
    expect(await screen.findByRole('heading', { level: 1, name: 'Analytics' })).toBeInTheDocument();
  });

  it('give a viewer the admins-only page', async () => {
    renderAt('viewer');
    expect(await screen.findByRole('heading', { name: 'Admins only' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 1, name: 'Analytics' })).not.toBeInTheDocument();
  });

  it('add an admin-only nav item next to Data & ops and honour only the time window', () => {
    expect(
      nav.map(({ label, path, order, adminOnly }) => ({ label, path, order, adminOnly })),
    ).toEqual([{ label: 'Analytics', path: '/admin/analytics', order: 930, adminOnly: true }]);
    expect(routes[0]?.handle).toEqual({ filters: { roundType: false, window: true } });
  });
});
