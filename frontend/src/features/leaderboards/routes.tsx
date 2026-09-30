import { Trophy } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { BOTH_FILTERS } from '../../lib/pageFilters';

import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: '/leaderboards',
    handle: { filters: BOTH_FILTERS },
    lazy: async () => {
      const { LeaderboardsPage } = await import('./pages/LeaderboardsPage');
      return { Component: LeaderboardsPage };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Leaderboards', path: '/leaderboards', icon: Trophy, order: 30, mobileTab: true },
];
