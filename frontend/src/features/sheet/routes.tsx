import type { RouteObject } from 'react-router';
import { NO_FILTERS } from '../../lib/pageFilters';

/** The Sunday Sheet (Plan 14): one issue per held Sunday. */
export const routes: RouteObject[] = [
  {
    path: '/sheet/:date',
    handle: { filters: NO_FILTERS },
    lazy: async () => ({ Component: (await import('./pages/SheetPage')).SheetPage }),
  },
];
