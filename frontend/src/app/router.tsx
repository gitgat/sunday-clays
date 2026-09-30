import { createBrowserRouter, type RouteObject } from 'react-router';
import { RequireRole } from '../features/auth/components/RequireRole';
import { SessionShell } from '../features/auth/components/SessionShell';
import { RouteErrorPage } from './ErrorBoundary';
import { featureRoutes } from './registry';

/** Feature routes marked `handle: { public: true }` (the login page) skip the session guard. */
function isPublic(route: RouteObject): boolean {
  return (route.handle as { public?: boolean } | undefined)?.public === true;
}

/**
 * The route tree: a root route, the public feature routes (rendered bare), then the session-guarded
 * AppShell layout route (Plan 07 T3: RequireRole → SessionShell → AppShell) holding every other
 * feature route. Only Plan 07 T2 (AppShell layout route) and Plan 07 T3 (RequireRole) may edit
 * this file (C10).
 * HydrateFallback sits on the root, above every public and guarded route: feature routes are
 * lazy, and without it React Router warns on the first load of every page.
 * The root errorElement catches unknown paths (404) and shell errors; the pathless route inside
 * the shell catches page errors, so the navigation stays usable.
 */
export const appRoutes: RouteObject[] = [
  {
    path: '/',
    HydrateFallback: () => null,
    errorElement: <RouteErrorPage />,
    children: [
      ...featureRoutes.filter(isPublic),
      {
        element: (
          <RequireRole>
            <SessionShell />
          </RequireRole>
        ),
        children: [
          { errorElement: <RouteErrorPage />, children: featureRoutes.filter((r) => !isPublic(r)) },
        ],
      },
    ],
  },
];

export function createAppRouter(): ReturnType<typeof createBrowserRouter> {
  return createBrowserRouter(appRoutes);
}
