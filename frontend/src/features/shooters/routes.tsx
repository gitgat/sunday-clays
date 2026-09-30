import { Users } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { BOTH_FILTERS, NO_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: '/shooters',
    handle: { filters: NO_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/ShootersPage')).ShootersPage }),
  },
  {
    path: '/shooters/:id',
    handle: { filters: BOTH_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/ProfilePage')).ProfilePage }),
  },
];

export const nav: NavItem[] = [
  { label: 'Shooters', path: '/shooters', icon: Users, order: 40, mobileTab: true },
];
