import { Trophy } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { NO_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: 'achievements',
    handle: { filters: NO_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/TrophyRoomPage')).TrophyRoomPage }),
  },
  {
    path: 'achievements/:code',
    handle: { filters: NO_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/TrophyDetailPage')).TrophyDetailPage }),
  },
];

export const nav: NavItem[] = [
  { label: 'Trophies', path: '/achievements', icon: Trophy, order: 70 },
];
