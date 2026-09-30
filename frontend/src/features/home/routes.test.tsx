import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { beforeAll, describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { latestEvent, seasonEvents } from './mocks';
import { routes } from './routes';

// /api/meta uses this feature's default handler on purpose; the events endpoints belong to features/events.
describe('home routes', () => {
  // The page's lazy turnout chart: warm, and awaited below, so it never resolves after the test.
  beforeAll(async () => {
    await import('./components/TurnoutChart');
  });

  it('serve the home page at /', async () => {
    server.use(
      http.get('*/api/events/:date', () => HttpResponse.json(latestEvent)),
      http.get('*/api/events', () => HttpResponse.json(seasonEvents)),
    );
    const router = createMemoryRouter(
      [{ path: '/', HydrateFallback: () => null, children: routes }],
      { initialEntries: ['/'] },
    );
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sunday Clays' }),
    ).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'Sep 27, 2026' })).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Turnout per Sunday' })).toBeInTheDocument();
  });
});
