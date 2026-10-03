import { ToggleRight } from 'lucide-react';
import type { RouteObject } from 'react-router';
import type { NavItem } from '../../app/registry';
import { NO_FILTERS } from '../../lib/pageFilters';
import { RequireRole } from '../auth/components/RequireRole';

// Admin pages render inside RequireRole role="admin"; the page stays lazy (C10).
export const routes: RouteObject[] = [
  {
    path: '/admin/features',
    handle: { filters: NO_FILTERS },
    lazy: async () => {
      const { FeaturesPage } = await import('./pages/FeaturesPage');
      return {
        element: (
          <RequireRole role="admin">
            <FeaturesPage />
          </RequireRole>
        ),
      };
    },
  },
];

export const nav: NavItem[] = [
  { label: 'Features', path: '/admin/features', icon: ToggleRight, order: 940, adminOnly: true },
];
