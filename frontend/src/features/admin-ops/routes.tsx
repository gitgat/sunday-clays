import { Wrench } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { NO_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';
import { RequireRole } from '../auth/components/RequireRole';

// Plan 07 D10 / Decision D13: admin pages render inside RequireRole role="admin"; the page stays lazy (C10).
export const routes: RouteObject[] = [
  {
    path: '/admin/ops',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { OpsPage } = await import('./pages/OpsPage');
      return {
        element: (
          <RequireRole role="admin">
            <OpsPage />
          </RequireRole>
        ),
      };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Data & ops', path: '/admin/ops', icon: Wrench, order: 920, adminOnly: true },
];
