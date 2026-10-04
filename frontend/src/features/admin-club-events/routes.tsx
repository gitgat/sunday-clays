import { CalendarCog } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { NO_FILTERS } from '../../lib/pageFilters';
import { RequireRole } from '../auth/components/RequireRole';

export const routes: RouteObject[] = [
  {
    path: '/admin/club-events',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { AdminClubEventsPage } = await import('./pages/AdminClubEventsPage');
      return {
        element: (
          <RequireRole role="admin">
            <AdminClubEventsPage />
          </RequireRole>
        ),
      };
    },
  },
];

export const nav: NavItem[] = [
  {
    label: 'Manage club events',
    path: '/admin/club-events',
    icon: CalendarCog,
    order: 915,
    adminOnly: true,
  },
];
