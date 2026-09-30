import { useQuery } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createTestQueryClient } from '../test/render';
import { RouteErrorPage } from './ErrorBoundary';
import { AppProviders } from './providers';

afterEach(() => {
  vi.restoreAllMocks();
});

function UsesQuery() {
  const { data } = useQuery({ queryKey: ['answer'], queryFn: () => Promise.resolve(42) });
  return <p>answer:{data ?? '…'}</p>;
}

function Boom(): never {
  throw new Error('kaboom');
}

describe('AppProviders', () => {
  it('provides a QueryClient to the tree', async () => {
    render(
      <AppProviders queryClient={createTestQueryClient()}>
        <UsesQuery />
      </AppProviders>,
    );
    expect(await screen.findByText('answer:42')).toBeInTheDocument();
  });

  it('shows the fallback instead of a blank page when a render throws, and logs the error', () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    render(
      <AppProviders queryClient={createTestQueryClient()}>
        <Boom />
      </AppProviders>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong');
    expect(screen.getByRole('link', { name: 'Go to home' })).toHaveAttribute('href', '/');
    expect(log).toHaveBeenCalled();
  });
});

describe('RouteErrorPage', () => {
  it('renders "Page not found" for an unknown path', async () => {
    const router = createMemoryRouter(
      [{ path: '/', element: <p>home</p>, errorElement: <RouteErrorPage /> }],
      {
        initialEntries: ['/nope'],
      },
    );
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });

  it('renders a generic message when a route throws', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const router = createMemoryRouter([
      { path: '/', element: <Boom />, errorElement: <RouteErrorPage /> },
    ]);
    render(<RouterProvider router={router} />);
    expect(
      await screen.findByRole('heading', { name: 'Something went wrong' }),
    ).toBeInTheDocument();
  });
});
