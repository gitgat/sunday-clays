import { Upload } from 'lucide-react';
import type { RouteObject } from 'react-router';
import { NO_FILTERS } from '../../lib/pageFilters';
import type { NavItem } from '../../app/registry';
import { RequireRole } from '../auth/components/RequireRole';

// Plan 07 D10 / Decision D13: admin pages render inside RequireRole role="admin"; the pages stay lazy (C10).
export const routes: RouteObject[] = [
  {
    path: '/admin',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { ImportsPage } = await import('./pages/ImportsPage');
      return {
        element: (
          <RequireRole role="admin">
            <ImportsPage />
          </RequireRole>
        ),
      };
    },
  },
  {
    path: '/admin/imports/:id',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { ImportDetailPage } = await import('./pages/ImportDetailPage');
      return {
        element: (
          <RequireRole role="admin">
            <ImportDetailPage />
          </RequireRole>
        ),
      };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Imports', path: '/admin', icon: Upload, order: 900, adminOnly: true },
];
