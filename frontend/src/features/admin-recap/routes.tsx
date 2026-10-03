import { Mail } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { NO_FILTERS } from '../../lib/pageFilters';
import { RequireRole } from '../auth/components/RequireRole';

export const routes: RouteObject[] = [
  {
    path: '/admin/recap',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { RecapPage } = await import('./pages/RecapPage');
      return {
        element: (
          <RequireRole role="admin">
            <RecapPage />
          </RequireRole>
        ),
      };
    },
  },
];

// Admins always see it (admin preview while weekly_recap is off); viewers never do.
export const nav: NavItem[] = [
  {
    label: 'Recap',
    path: '/admin/recap',
    icon: Mail,
    order: 935,
    adminOnly: true,
    feature: 'weekly_recap',
  },
];
