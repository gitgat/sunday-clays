import { Landmark } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { BOTH_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: '/club',
    handle: { filters: BOTH_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/ClubPage')).ClubPage }),
  },
];

export const nav: NavItem[] = [{ label: 'Club', path: '/club', icon: Landmark, order: 50 }];
