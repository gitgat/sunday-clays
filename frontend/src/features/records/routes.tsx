import { Medal } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { BOTH_FILTERS } from '../../lib/pageFilters';

import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: '/records',
    handle: { filters: BOTH_FILTERS },
    lazy: async () => {
      const { RecordsPage } = await import('./pages/RecordsPage');
      return { Component: RecordsPage };
    },
  },
];

export const nav: NavItem[] = [{ label: 'Records', path: '/records', icon: Medal, order: 120 }];
