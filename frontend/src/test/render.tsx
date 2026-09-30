import { QueryClient } from '@tanstack/react-query';
import { render, type RenderResult } from '@testing-library/react';
import userEvent, { type UserEvent } from '@testing-library/user-event';
import type { ReactElement } from 'react';
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router';
import { AppProviders } from '../app/providers';
import { appRoutes } from '../app/router';
import { SESSION_QUERY_KEY, type Role } from '../features/auth/api';

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  });
}

export interface RenderOptions {
  /** Initial URL (path + query), default '/'. */
  route?: string;
  /** Route pattern `ui` is mounted at (renderWithProviders only), default '*'. */
  path?: string;
  queryClient?: QueryClient;
  /**
   * Seeds the session query: 'viewer' (default), 'admin', null (logged out), or 'unset' to leave
   * it empty so it is fetched from the MSW /api/auth/me handler.
   */
  role?: Role | null | 'unset';
}

export interface ProvidersResult extends RenderResult {
  user: UserEvent;
  queryClient: QueryClient;
  router: ReturnType<typeof createMemoryRouter>;
}

/** Renders a route tree in a memory router inside the production provider stack. */
export function renderRoutes(routes: RouteObject[], options: RenderOptions = {}): ProvidersResult {
  const queryClient = options.queryClient ?? createTestQueryClient();
  const role = options.role === undefined ? 'viewer' : options.role;
  if (role !== 'unset') {
    queryClient.setQueryData(SESSION_QUERY_KEY, role === null ? null : { role });
  }
  const router = createMemoryRouter(routes, { initialEntries: [options.route ?? '/'] });
  const user = userEvent.setup();
  const result = render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { ...result, user, queryClient, router };
}

/** Renders one element at `path` (default '*') with router, query client, session and boundary. */
export function renderWithProviders(
  ui: ReactElement,
  options: RenderOptions = {},
): ProvidersResult {
  return renderRoutes([{ path: options.path ?? '*', element: ui }], options);
}

/** Plan 01 T2's helper, kept: the real route tree at `route` (lazy pages need findBy* queries). */
export function renderRoute(route: string, routes: RouteObject[] = appRoutes): ProvidersResult {
  return renderRoutes(routes, { route });
}
