import { House, Trophy } from 'lucide-react';
import { describe, expect, it } from 'vitest';

import type { RouteObject } from 'react-router';
import { BOTH_FILTERS, NO_FILTERS, ROUND_TYPE_ONLY, type PageFilters } from '../lib/pageFilters';
import { collectFeatures, featureRoutes, navItems, type FeatureModule } from './registry';

describe('collectFeatures', () => {
  it('flattens routes in feature path order and sorts nav by order', () => {
    const modules: Record<string, FeatureModule> = {
      '../features/zeta/routes.tsx': {
        routes: [{ path: 'zeta' }],
        nav: [{ label: 'Zeta', path: '/zeta', icon: Trophy, order: 120 }],
      },
      '../features/alpha/routes.tsx': {
        routes: [{ path: 'alpha' }, { path: 'alpha/:id' }],
        nav: [{ label: 'Alpha', path: '/alpha', icon: House, order: 20 }],
      },
      '../features/beta/routes.tsx': { routes: [{ path: 'beta' }] },
    };

    const { routes, nav } = collectFeatures(modules);

    expect(routes.map((r) => r.path)).toEqual(['alpha', 'alpha/:id', 'beta', 'zeta']);
    expect(nav.map((n) => n.label)).toEqual(['Alpha', 'Zeta']);
  });

  it('returns empty lists when no feature exists', () => {
    expect(collectFeatures({})).toEqual({ routes: [], nav: [] });
  });

  it.each([
    ['has no routes export', {}],
    ['exports routes that are not an array', { routes: { path: 'broken' } }],
  ])('names a feature module that %s', (_case, module) => {
    const modules = {
      '../features/alpha/routes.tsx': { routes: [{ path: 'alpha' }] },
      '../features/broken/routes.tsx': module as unknown as FeatureModule,
    };

    expect(() => collectFeatures(modules)).toThrow(
      new TypeError('../features/broken/routes.tsx must export routes'),
    );
    expect(() => collectFeatures(modules)).toThrow(TypeError);
  });
});

describe('the discovered registry', () => {
  it('includes the home feature as the index route and first nav item', () => {
    expect(featureRoutes.some((route) => route.index === true)).toBe(true);
    expect(navItems[0]).toMatchObject({ label: 'Home', path: '/', order: 10, mobileTab: true });
  });
});

/** A route's URL pattern as a leading-slash path ('/' for the index route). */
function urlOf(route: RouteObject): string {
  if (route.index === true) return '/';
  const path = route.path ?? '';
  return path.startsWith('/') ? path : `/${path}`;
}

/**
 * Which global filters each page honours (owner 2026-09-29: show only the filters a page accepts). Audited
 * against the hooks each page reads: useRoundTypes / round_type on its queries, useTimeWindow and windowed
 * chart scopes. Pages that only carry `?rt=` on their links (an event page, the shooter list, Trophies) honour neither.
 */
const EXPECTED: Record<string, PageFilters> = {
  '/': BOTH_FILTERS,
  '/events': ROUND_TYPE_ONLY,
  '/events/:date': NO_FILTERS,
  '/shooters': NO_FILTERS,
  '/shooters/:id': BOTH_FILTERS,
  '/leaderboards': BOTH_FILTERS,
  '/race': BOTH_FILTERS,
  '/records': BOTH_FILTERS,
  '/club': BOTH_FILTERS,
  '/about': NO_FILTERS,
  '/explorer': BOTH_FILTERS,
  '/stations': BOTH_FILTERS,
  '/weather': BOTH_FILTERS,
  '/achievements': NO_FILTERS,
  '/achievements/:code': NO_FILTERS,
  '/yir': ROUND_TYPE_ONLY,
  '/yir/:year': ROUND_TYPE_ONLY,
  '/yir/:year/shooters/:id': ROUND_TYPE_ONLY,
  '/admin': NO_FILTERS,
  '/admin/imports/:id': NO_FILTERS,
  '/admin/identity': NO_FILTERS,
  '/admin/ops': NO_FILTERS,
  '/admin/analytics': { roundType: false, window: true },
  '/admin/features': NO_FILTERS,
  '/login': NO_FILTERS,
};

describe('page filter declarations', () => {
  it('gives every feature route a declaration', () => {
    for (const route of featureRoutes) {
      const filters = (route.handle as { filters?: PageFilters } | undefined)?.filters;
      expect(filters, urlOf(route)).toEqual({
        roundType: expect.any(Boolean) as unknown,
        window: expect.any(Boolean) as unknown,
      });
    }
  });

  it('declares the audited filters for every page, and lists no page that does not exist', () => {
    const declared = Object.fromEntries(
      featureRoutes.map((route) => [
        urlOf(route),
        (route.handle as { filters: PageFilters }).filters,
      ]),
    );
    expect(declared).toEqual(EXPECTED);
  });
});
