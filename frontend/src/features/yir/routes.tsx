import { CalendarRange } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { ROUND_TYPE_ONLY } from '../../lib/pageFilters';

/**
 * Year in Review is about a chosen year, so no page follows the time window; the year picker is
 * its date control. Every figure on every page follows the round-type filter.
 */
export const routes: RouteObject[] = [
  {
    path: '/yir',
    handle: { filters: ROUND_TYPE_ONLY },
    lazy: () => import('./pages/YirIndexPage').then((m) => ({ Component: m.YirIndexPage })),
  },
  {
    path: '/yir/:year',
    handle: { filters: ROUND_TYPE_ONLY },
    lazy: () => import('./pages/YirClubPage').then((m) => ({ Component: m.YirClubPage })),
  },
  {
    path: '/yir/:year/shooters/:id',
    handle: { filters: ROUND_TYPE_ONLY },
    lazy: () => import('./pages/YirShooterPage').then((m) => ({ Component: m.YirShooterPage })),
  },
];

export const nav: NavItem[] = [
  { label: 'Year in Review', path: '/yir', icon: CalendarRange, order: 110 },
];
