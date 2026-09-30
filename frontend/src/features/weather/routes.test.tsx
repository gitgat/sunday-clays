import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { describe, expect, it } from 'vitest';
import { profileSection } from './profileSection';
import { nav, routes } from './routes';

describe('weather feature registration', () => {
  it('serves the lazy weather page at /weather with its nav item', async () => {
    // A parent route with a HydrateFallback, as in the app's layout route (and Plan 08's route
    // tests), so the lazy child loads without React Router's "no HydrateFallback" warning.
    const router = createMemoryRouter(
      [{ path: '/', HydrateFallback: () => null, children: routes }],
      { initialEntries: ['/weather'] },
    );
    render(
      <QueryClientProvider client={new QueryClient()}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    // The first findBy waits for the lazy page chunk, which is slow when the whole suite runs in parallel.
    expect(
      await screen.findByRole('heading', { name: 'Weather', level: 1 }, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Scores by conditions' })).toBeInTheDocument();
    expect(
      await screen.findByRole('region', { name: 'Turnout by conditions' }),
    ).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Weather sensitivity' })).toBeInTheDocument();
    expect(nav).toEqual([expect.objectContaining({ path: '/weather', order: 90 })]);
  });

  it('adds the weather sensitivity section to profiles', async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <profileSection.Component shooterId={59} />
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/Wind gusts: −0.6 targets/)).toBeInTheDocument();
  });
});
