import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../test/lazyChart';
import { server } from '../../test/msw/server';
import { clubDistribution } from './mocks';
import { routes } from './routes';

function renderAt(path: string) {
  const router = createMemoryRouter(
    [{ path: '/', HydrateFallback: () => null, children: routes }],
    {
      initialEntries: [path],
    },
  );
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

// These tests use this feature's default handlers (./mocks, merged into the global MSW server) on purpose.
describe('shooters routes', () => {
  it('serve the directory at /shooters', async () => {
    renderAt('/shooters');
    expect(await screen.findByRole('heading', { level: 1, name: 'Shooters' })).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: /Gilchrist, Melvin/ })).toBeInTheDocument();
  });

  it(
    'serve the profile at /shooters/:id',
    async () => {
      // The club feature owns /api/club/*, so this feature's default handlers do not answer it.
      server.use(http.get('*/api/club/distribution', () => HttpResponse.json(clubDistribution)));
      renderAt('/shooters/3');
      expect(
        await screen.findByRole('heading', { level: 1, name: 'Hadley, Ike' }, LAZY_CHART),
      ).toBeInTheDocument();
      expect(await screen.findByText('Hot (+3.4)', {}, LAZY_CHART)).toBeInTheDocument();
      expect(await screen.findAllByRole('button', { name: 'CSV' }, LAZY_CHART)).not.toHaveLength(0);
    },
    LAZY_TEST_TIMEOUT,
  );
});
