import { CalendarHeart } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { FeatureGate } from '../../components/FeatureGate';
import { NO_FILTERS } from '../../lib/pageFilters';

/** Plan 20 §5.7.1: two lazy pages behind the `events` launch switch (Plan 19 FeatureGate). */
export const routes: RouteObject[] = [
  {
    path: '/club-events',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { ClubEventsPage } = await import('./pages/ClubEventsPage');
      return {
        element: (
          <FeatureGate feature="events">
            <ClubEventsPage />
          </FeatureGate>
        ),
      };
    },
  },
  {
    path: '/club-events/:id',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { ClubEventPage } = await import('./pages/ClubEventPage');
      return {
        element: (
          <FeatureGate feature="events">
            <ClubEventPage />
          </FeatureGate>
        ),
      };
    },
  },
];

/** After Events (20), before Leaderboards (30); in the phone's "More" list, not a tab. */
export const nav: NavItem[] = [
  { label: 'Club events', path: '/club-events', icon: CalendarHeart, order: 25, feature: 'events' },
];
