import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderRoutes } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { SESSION_QUERY_KEY } from '../api';
import { RequireRole } from './RequireRole';
import { SessionShell } from './SessionShell';

const ROUTES = [
  { path: '/login', element: <p>login page</p> },
  {
    path: '/',
    element: (
      <RequireRole>
        <SessionShell />
      </RequireRole>
    ),
    children: [{ index: true, element: <p>home page</p> }],
  },
];

const LOGOUT_FAILURES: [string, () => Response][] = [
  ['a network error', () => HttpResponse.error()],
  [
    'a server error',
    () =>
      HttpResponse.json({ error: { code: 'http_503', message: 'Unavailable' } }, { status: 503 }),
  ],
];

afterEach(() => {
  vi.restoreAllMocks();
});

describe('SessionShell', () => {
  it('shows who is signed in and logs out to the login page, forgetting cached data', async () => {
    stubViewport('desktop');
    let loggedOut = false;
    server.use(
      http.post('/api/auth/logout', () => {
        loggedOut = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user, router, queryClient } = renderRoutes(ROUTES, { route: '/', role: 'admin' });
    queryClient.setQueryData(['/api/events'], ['cached']);
    expect(screen.getByText('Signed in as admin')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Log out' }));
    expect(await screen.findByText('login page')).toBeInTheDocument();
    expect(loggedOut).toBe(true);
    expect(router.state.location.pathname).toBe('/login');
    expect(queryClient.getQueryData(['/api/events'])).toBeUndefined();
  });

  // Sessions are signed cookies that only the server can clear (httpOnly): showing /login after a
  // failed logout would leave the next person on a shared device signed in as this one.
  it.each(LOGOUT_FAILURES)(
    'keeps the session and says so when logging out fails with %s, then retries',
    async (_label, fail) => {
      stubViewport('desktop');
      let calls = 0;
      server.use(
        http.post('/api/auth/logout', () => {
          calls += 1;
          return calls === 1 ? fail() : new HttpResponse(null, { status: 204 });
        }),
      );
      const { user, router, queryClient } = renderRoutes(ROUTES, { route: '/', role: 'viewer' });
      queryClient.setQueryData(['/api/events'], ['cached']);
      await user.click(screen.getByRole('button', { name: 'Log out' }));
      expect(await screen.findByRole('alert')).toHaveTextContent(
        "Couldn't log out. Check your connection and try again.",
      );
      expect(router.state.location.pathname).toBe('/');
      expect(screen.getByText('home page')).toBeInTheDocument();
      expect(queryClient.getQueryData(SESSION_QUERY_KEY)).toEqual({ role: 'viewer' });
      expect(queryClient.getQueryData(['/api/events'])).toBeUndefined();

      await user.click(screen.getByRole('button', { name: 'Log out' }));
      expect(await screen.findByText('login page')).toBeInTheDocument();
      expect(calls).toBe(2);
    },
  );

  it('treats a 401 from logout as already logged out', async () => {
    stubViewport('desktop');
    server.use(
      http.post('/api/auth/logout', () =>
        HttpResponse.json(
          { error: { code: 'unauthenticated', message: 'Log in to continue' } },
          { status: 401 },
        ),
      ),
    );
    const { user, router, queryClient } = renderRoutes(ROUTES, { route: '/', role: 'viewer' });
    await user.click(screen.getByRole('button', { name: 'Log out' }));
    expect(await screen.findByText('login page')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/login');
    expect(queryClient.getQueryData(SESSION_QUERY_KEY)).toBeNull();
  });

  it('puts the account panel in the More sheet on mobile and logs out from there', async () => {
    stubViewport('mobile');
    const { user, router } = renderRoutes(ROUTES, { route: '/', role: 'viewer' });
    expect(screen.queryByText('Signed in as viewer')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'More' }));
    expect(screen.getByText('Signed in as viewer')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Log out' }));
    expect(await screen.findByText('login page')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/login');
  });

  it('falls back to the viewer account when no session is cached (never admin)', () => {
    stubViewport('desktop');
    renderRoutes(
      [{ path: '/', element: <SessionShell />, children: [{ index: true, element: <p>home</p> }] }],
      { route: '/', role: null },
    );
    expect(screen.getByText('Signed in as viewer')).toBeInTheDocument();
  });
});
