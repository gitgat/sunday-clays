import { describe, expect, it } from 'vitest';

import { LAZY_CHART } from '../../test/lazyChart';
import { AboutPage } from './pages/AboutPage';
import { nav, routes } from './routes';

describe('about routes', () => {
  it(
    'lazily loads AboutPage at /about',
    async () => {
      const [route] = routes;
      expect(route?.path).toBe('/about');
      if (typeof route?.lazy !== 'function') throw new Error('expected a lazy route function');
      await expect(route.lazy()).resolves.toMatchObject({ Component: AboutPage });
    },
    LAZY_CHART.timeout,
  );

  it('registers About in the nav for everyone, in the More sheet', () => {
    expect(nav).toEqual([expect.objectContaining({ label: 'About', path: '/about', order: 140 })]);
    expect(nav[0]?.adminOnly).not.toBe(true);
    expect(nav[0]?.mobileTab).not.toBe(true);
  });
});
