import { House } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { BOTH_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';

/** Home (Plan 08 T4): latest event, club pulse, the "me" panel and the homeWidget glob host. */
export const routes: RouteObject[] = [
  {
    index: true,
    handle: { filters: BOTH_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/HomePage')).HomePage }),
  },
];

export const nav: NavItem[] = [
  { label: 'Home', path: '/', icon: House, order: 10, mobileTab: true },
];
