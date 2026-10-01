import { ChartColumn } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import type { PageFilters } from '../../lib/pageFilters';
import { RequireRole } from '../auth/components/RequireRole';

/** The header shows only the time window: these counts have no round type (Decision 18). */
const WINDOW_ONLY: PageFilters = { roundType: false, window: true };

// Admin pages render inside RequireRole role="admin"; the page stays lazy (C10).
export const routes: RouteObject[] = [
  {
    path: '/admin/analytics',
    handle: { filters: WINDOW_ONLY },
    lazy: async () => {
      const { AnalyticsPage } = await import('./pages/AnalyticsPage');
      return {
        element: (
          <RequireRole role="admin">
            <AnalyticsPage />
          </RequireRole>
        ),
      };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Analytics', path: '/admin/analytics', icon: ChartColumn, order: 930, adminOnly: true },
];
