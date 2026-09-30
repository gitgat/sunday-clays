import { describe, expect, it } from 'vitest';
import { nav, routes } from './routes';

describe('achievements routes', () => {
  it('lazily registers the Trophy Room and trophy pages', async () => {
    // Relative children of the `/` root (Plan 01 Decision 15); served at /achievements[/:code].
    expect(routes.map((route) => route.path)).toEqual(['achievements', 'achievements/:code']);
    for (const route of routes) {
      const lazy = route.lazy;
      expect(typeof lazy).toBe('function');
      if (typeof lazy === 'function') {
        const loaded = await lazy();
        expect(typeof loaded.Component).toBe('function');
      }
    }
  });

  it('adds the Trophies nav item at order 70', () => {
    expect(nav).toEqual([
      expect.objectContaining({ label: 'Trophies', path: '/achievements', order: 70 }),
    ]);
  });
});
