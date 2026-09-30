import { CloudSun } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { BOTH_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';

export const routes: RouteObject[] = [
  {
    path: '/weather',
    handle: { filters: BOTH_FILTERS },
    lazy: () => import('./pages/WeatherPage').then((m) => ({ Component: m.WeatherPage })),
  },
];

export const nav: NavItem[] = [{ label: 'Weather', path: '/weather', icon: CloudSun, order: 90 }];
