import { Compass } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { BOTH_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: 'explorer',
    handle: { filters: BOTH_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/ExplorerPage')).ExplorerPage }),
  },
];

export const nav: NavItem[] = [{ label: 'Explorer', path: '/explorer', icon: Compass, order: 60 }];
