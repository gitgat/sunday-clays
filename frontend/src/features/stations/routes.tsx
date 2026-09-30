import { Target } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { BOTH_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: 'stations',
    handle: { filters: BOTH_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/StationsPage')).StationsPage }),
  },
];

export const nav: NavItem[] = [{ label: 'Stations', path: '/stations', icon: Target, order: 80 }];
