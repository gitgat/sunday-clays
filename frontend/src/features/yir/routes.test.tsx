import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { describe, expect, it } from 'vitest';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../test/lazyChart';
import { server } from '../../test/msw/server';
import { leaderboardHandler } from './mocks';
import { nav, routes } from './routes';
import { ROUND_TYPE_ONLY } from '../../lib/pageFilters';

function renderAt(path: string) {
  // A parent route with a HydrateFallback, as in the app's layout route (and Plan 08's route
  // tests), so the lazy children load without React Router's "no HydrateFallback" warning.
  const router = createMemoryRouter(
    [
      {
        path: '/',
        HydrateFallback: () => null,
        children: routes,
      },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

describe('year in review registration', () => {
  it(
    'redirects /yir to the latest year on the default handlers',
    async () => {
      server.use(leaderboardHandler);
      const router = renderAt('/yir');
      expect(
        await screen.findByRole('heading', { name: 'Year in Review 2026' }, LAZY_CHART),
      ).toBeInTheDocument();
      expect(router.state.location.pathname).toBe('/yir/2026');
      expect(nav).toEqual([expect.objectContaining({ path: '/yir', order: 110 })]);
    },
    LAZY_TEST_TIMEOUT,
  );

  it('declares the filters each page follows: round type only, no time window', () => {
    const filters = Object.fromEntries(
      routes.map((r) => [r.path, (r.handle as { filters: unknown }).filters]),
    );
    expect(filters).toEqual({
      '/yir': ROUND_TYPE_ONLY,
      '/yir/:year': ROUND_TYPE_ONLY,
      '/yir/:year/shooters/:id': ROUND_TYPE_ONLY,
    });
    expect(ROUND_TYPE_ONLY).toEqual({ roundType: true, window: false });
  });

  it('serves the shooter page', async () => {
    renderAt('/yir/2025/shooters/307');
    expect(
      await screen.findByRole('region', { name: 'Grimsby, Gregor: 2025' }),
    ).toBeInTheDocument();
  });
});
