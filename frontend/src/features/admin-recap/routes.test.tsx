import { describe, expect, it } from 'vitest';
import { nav, routes } from './routes';

describe('admin-recap routes', () => {
  it('adds an admin-only Recap nav item at 935, named for its switch', () => {
    expect(
      nav.map(({ label, path, order, adminOnly, feature }) => ({
        label,
        path,
        order,
        adminOnly,
        feature,
      })),
    ).toEqual([
      {
        label: 'Recap',
        path: '/admin/recap',
        order: 935,
        adminOnly: true,
        feature: 'weekly_recap',
      },
    ]);
    expect(routes[0]?.handle).toEqual({ filters: { roundType: false, window: false } });
  });

  it('lazily registers the admin-gated page', async () => {
    const lazy = routes[0]?.lazy;
    expect(typeof lazy).toBe('function');
    if (typeof lazy === 'function') {
      const loaded = await lazy();
      expect(loaded.element).toBeTruthy();
    }
  });
});
