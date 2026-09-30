import { Flag } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { BOTH_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: '/race',
    // Race opens on 12 months when the URL has no `w` (see PAGE_DEFAULT_WINDOWS).
    handle: { filters: BOTH_FILTERS },
    lazy: async () => {
      const { RacePage } = await import('./pages/RacePage');
      return { Component: RacePage };
    },
  },
];

export const nav: NavItem[] = [{ label: 'Race', path: '/race', icon: Flag, order: 130 }];
