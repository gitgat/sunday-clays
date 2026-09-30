import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { beforeAll, describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { routes } from './routes';

// Uses this feature's default handlers (./mocks) on purpose; /api/explore belongs to the explorer feature.
describe('club routes', { timeout: 15_000 }, () => {
  // The page loads its charts (and ECharts) lazily: warm those chunks so a cold import under a
  // busy test run never eats the findBy budget.
  beforeAll(async () => {
    await Promise.all([
      import('./components/ClubCharts'),
      import('./components/TurnoutWeatherCard'),
    ]);
  });

  it('serve the dashboard at /club', async () => {
    server.use(
      http.post('*/api/explore', () =>
        HttpResponse.json({ columns: [], rows: [], n_rounds: 0, truncated: false }),
      ),
    );
    const router = createMemoryRouter(
      [{ path: '/', HydrateFallback: () => null, children: routes }],
      {
        initialEntries: ['/club'],
      },
    );
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(await screen.findByRole('heading', { level: 1, name: 'Club' })).toBeInTheDocument();
    // The chart renders behind a lazy chunk and an ECharts init: allow for a busy test run.
    expect(
      await screen.findByRole('img', { name: 'Attendance per Sunday chart' }, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(await screen.findByText('Core regulars (2)')).toBeInTheDocument();
  });
});
