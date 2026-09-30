import { useQuery } from '@tanstack/react-query';
import { screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it } from 'vitest';
import { api, setNavigate, unwrap } from '../../api/client';
import { server } from '../../test/msw/server';
import { renderRoutes } from '../../test/render';
import { SESSION_QUERY_KEY, onSessionExpired } from './api';
import { LoginPage } from './pages/LoginPage';

/** A page whose data request gets a 401: the cookie died while the app still holds a role. */
function Probe() {
  const { isError } = useQuery({
    queryKey: ['/api/health'],
    queryFn: () => unwrap(api.GET('/api/health')),
  });
  return <p>{isError ? 'probe failed' : 'probe loading'}</p>;
}

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('onSessionExpired', () => {
  it('lands a data 401 on the login page with next and stays there (no redirect loop)', async () => {
    let calls = 0;
    server.use(
      http.get('/api/health', () => {
        calls += 1;
        return HttpResponse.json(
          { error: { code: 'unauthenticated', message: 'x' } },
          { status: 401 },
        );
      }),
    );
    // The client builds next from window.location, which the browser router keeps in sync.
    window.history.replaceState(null, '', '/events');
    const { router, queryClient } = renderRoutes(
      [
        { path: '/login', element: <LoginPage /> },
        { path: '/events', element: <Probe /> },
      ],
      { route: '/events', role: 'viewer' },
    );
    setNavigate(onSessionExpired(queryClient, (to) => void router.navigate(to)));
    expect(await screen.findByLabelText('Password')).toBeInTheDocument();
    expect(router.state.location.pathname + router.state.location.search).toBe(
      '/login?next=%2Fevents',
    );
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(router.state.location.pathname).toBe('/login');
    expect(calls).toBe(1);
    expect(queryClient.getQueryData(SESSION_QUERY_KEY)).toBeNull();
  });
});
