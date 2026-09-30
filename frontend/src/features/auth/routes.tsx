import type { RouteObject } from 'react-router';
import { NO_FILTERS } from '../../lib/pageFilters';

/** `handle.public` routes render outside RequireRole and the AppShell (see app/router.tsx). */
export const routes: RouteObject[] = [
  {
    path: 'login',
    handle: { public: true, filters: NO_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/LoginPage')).LoginPage }),
  },
];
