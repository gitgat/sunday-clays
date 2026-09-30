import { describe, expect, it } from 'vitest';
import { nav, routes } from './routes';

describe('stations routes', () => {
  it('lazily registers the stations page', async () => {
    // A relative child of the `/` root (Plan 01 Decision 15); served at /stations.
    expect(routes.map((route) => route.path)).toEqual(['stations']);
    const lazy = routes[0]?.lazy;
    expect(typeof lazy).toBe('function');
    if (typeof lazy === 'function') {
      const loaded = await lazy();
      expect(typeof loaded.Component).toBe('function');
    }
  });

  it('adds the Stations nav item at order 80', () => {
    expect(nav).toEqual([
      expect.objectContaining({ label: 'Stations', path: '/stations', order: 80 }),
    ]);
  });
});
