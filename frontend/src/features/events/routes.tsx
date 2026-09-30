import { CalendarDays } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { NO_FILTERS, ROUND_TYPE_ONLY } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';

/** Calendar + list and the event page (C10: lazy routes, Events nav at order 20, a mobile tab). */
export const routes: RouteObject[] = [
  {
    path: '/events',
    handle: { filters: ROUND_TYPE_ONLY },
    lazy: async () => ({ Component: (await import('./pages/EventsPage')).EventsPage }),
  },
  {
    path: '/events/:date',
    handle: { filters: NO_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/EventDetailPage')).EventDetailPage }),
  },
];

export const nav: NavItem[] = [
  { label: 'Events', path: '/events', icon: CalendarDays, order: 20, mobileTab: true },
];
