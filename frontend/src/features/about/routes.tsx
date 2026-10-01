import { Info } from 'lucide-react';
import type { RouteObject } from 'react-router';

import type { NavItem } from '../../app/registry';
import { NO_FILTERS } from '../../lib/pageFilters';

export const routes: RouteObject[] = [
  {
    path: '/about',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { AboutPage } = await import('./pages/AboutPage');
      return { Component: AboutPage };
    },
  },
];

export const nav: NavItem[] = [{ label: 'About', path: '/about', icon: Info, order: 140 }];
