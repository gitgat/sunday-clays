import { screen, waitFor } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderRoutes } from '../../../test/render';
import { SESSION_QUERY_KEY } from '../api';
import { RequireRole } from './RequireRole';

function routes(role?: 'viewer' | 'admin') {
  return [
    { path: '/login', element: <p>login page</p> },
    {
      path: '/events',
      element: (
        <RequireRole {...(role ? { role } : {})}>
          <p>secret</p>
        </RequireRole>
      ),
    },
  ];
}

describe('RequireRole', () => {
  it('renders children for a signed-in viewer', () => {
    renderRoutes(routes(), { route: '/events', role: 'viewer' });
    expect(screen.getByText('secret')).toBeInTheDocument();
  });

  it('sends a signed-out visitor to /login with next = path + query', () => {
    const { router } = renderRoutes(routes(), { route: '/events?rt=sporting', role: null });
    expect(router.state.location.pathname).toBe('/login');
    expect(router.state.location.search).toBe('?next=%2Fevents%3Frt%3Dsporting');
    expect(screen.getByText('login page')).toBeInTheDocument();
  });

  it('shows Admins only to a viewer on an admin page', () => {
    renderRoutes(routes('admin'), { route: '/events', role: 'viewer' });
    expect(screen.getByRole('heading', { name: 'Admins only' })).toBeInTheDocument();
    expect(screen.queryByText('secret')).toBeNull();
  });

  it('lets an admin through an admin page', () => {
    renderRoutes(routes('admin'), { route: '/events', role: 'admin' });
    expect(screen.getByText('secret')).toBeInTheDocument();
  });

  it('shows a loading state until the server answers', async () => {
    server.use(
      http.get('/api/auth/me', async () => {
        await delay(20);
        return HttpResponse.json({ role: 'viewer' });
      }),
    );
    renderRoutes(routes(), { route: '/events', role: 'unset' });
    expect(screen.getByRole('status', { name: 'Checking your session' })).toBeInTheDocument();
    expect(await screen.findByText('secret')).toBeInTheDocument();
  });

  it('offers a retry when the session check fails', async () => {
    let calls = 0;
    server.use(
      http.get('/api/auth/me', () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({}, { status: 503 })
          : HttpResponse.json({ role: 'viewer' });
      }),
    );
    const { user } = renderRoutes(routes(), { route: '/events', role: 'unset' });
    expect(
      await screen.findByRole('heading', { name: "Can't reach the server" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('secret')).toBeInTheDocument();
  });

  it('keeps the page when a background session refresh fails (e.g. on reconnect)', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({}, { status: 503 })));
    const { queryClient } = renderRoutes(routes(), { route: '/events', role: 'viewer' });
    await queryClient.refetchQueries({ queryKey: SESSION_QUERY_KEY });
    await waitFor(() => {
      expect(queryClient.getQueryState(SESSION_QUERY_KEY)?.status).toBe('error');
    });
    expect(screen.getByText('secret')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: "Can't reach the server" })).toBeNull();
  });
});
