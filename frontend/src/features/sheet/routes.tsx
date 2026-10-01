import type { RouteObject } from 'react-router';
import { ROUND_TYPE_ONLY } from '../../lib/pageFilters';

/** The Sunday Sheet (Plan 14): one issue per held Sunday. */
export const routes: RouteObject[] = [
  {
    path: '/sheet/:date',
    handle: { filters: ROUND_TYPE_ONLY },
    lazy: async () => ({ Component: (await import('./pages/SheetPage')).SheetPage }),
  },
];
