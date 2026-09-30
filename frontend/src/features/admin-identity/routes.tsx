import { UserCog } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { NO_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';
import { RequireRole } from '../auth/components/RequireRole';

// Plan 07 D10 / Decision D13: admin pages render inside RequireRole role="admin"; the page stays lazy (C10).
export const routes: RouteObject[] = [
  {
    path: '/admin/identity',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { IdentityPage } = await import('./pages/IdentityPage');
      return {
        element: (
          <RequireRole role="admin">
            <IdentityPage />
          </RequireRole>
        ),
      };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Identity', path: '/admin/identity', icon: UserCog, order: 910, adminOnly: true },
];
