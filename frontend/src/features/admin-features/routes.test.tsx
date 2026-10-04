import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderRoutes } from '../../test/render';
import { nav, routes } from './routes';

describe('admin-features routes', () => {
  it('serve the Features page to an admin', async () => {
    renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], {
      route: '/admin/features',
      role: 'admin',
    });
    expect(await screen.findByRole('heading', { level: 1, name: 'Features' })).toBeInTheDocument();
  });

  it('give a viewer the admins-only page', async () => {
    renderRoutes([{ path: '/', HydrateFallback: () => null, children: routes }], {
      route: '/admin/features',
      role: 'viewer',
    });
    expect(await screen.findByRole('heading', { name: 'Admins only' })).toBeInTheDocument();
  });

  it('add an admin-only Features nav item at 940 with no header filters', () => {
    expect(
      nav.map(({ label, path, order, adminOnly }) => ({ label, path, order, adminOnly })),
    ).toEqual([{ label: 'Features', path: '/admin/features', order: 940, adminOnly: true }]);
    expect(routes[0]?.handle).toEqual({ filters: { roundType: false, window: false } });
  });
});
