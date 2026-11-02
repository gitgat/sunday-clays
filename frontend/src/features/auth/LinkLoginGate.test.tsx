import type { QueryClient } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { AppProviders } from '../../app/providers';
import { server } from '../../test/msw/server';
import { createTestQueryClient } from '../../test/render';
import { SESSION_QUERY_KEY } from './api';
import { LinkLoginGate } from './components/LinkLoginGate';
import {
  captureLinkPassword,
  LINK_FAILED_KEY,
  resolveLinkLogin,
  takePendingLinkPassword,
} from './linkLogin';
import { TEST_PASSWORDS } from './mocks';
import { LoginPage } from './pages/LoginPage';
import { RequireRole } from './components/RequireRole';

const UNAVAILABLE_NOTE = "We couldn't check that link. Try opening it again in a moment.";

const loggedOut = http.get('/api/auth/me', () =>
  HttpResponse.json({ error: { code: 'unauthenticated', message: 'Log in' } }, { status: 401 }),
);

function setup(url: string, queryClient: QueryClient = createTestQueryClient()) {
  window.history.replaceState(null, '', url);
  captureLinkPassword();
  const ready = resolveLinkLogin(queryClient);
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginPage /> },
      {
        path: '/events/:id',
        element: (
          <RequireRole>
            <p>protected page</p>
          </RequireRole>
        ),
      },
    ],
    { initialEntries: [window.location.pathname + window.location.search] },
  );
  const visited: string[] = [];
  router.subscribe((state) => visited.push(state.location.pathname));
  const view = render(
    <AppProviders queryClient={queryClient}>
      <LinkLoginGate ready={ready}>
        <RouterProvider router={router} />
      </LinkLoginGate>
    </AppProviders>,
  );
  return { router, visited, queryClient, unmount: view.unmount };
}

function spyLinkLogin() {
  const bodies: unknown[] = [];
  server.use(
    http.post('/api/auth/link-login', async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json({ role: 'viewer' });
    }),
  );
  return bodies;
}

afterEach(() => {
  takePendingLinkPassword();
  window.history.replaceState(null, '', '/');
});

describe('link login', () => {
  it('logs in, shows the page and never flashes the login page', async () => {
    server.use(loggedOut);
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    const { visited, router, queryClient } = setup(
      `/events/1?p=${TEST_PASSWORDS.viewer}&rt=sporting`,
    );
    expect(window.location.search).toBe('?rt=sporting');
    expect(await screen.findByText('protected page')).toBeInTheDocument();
    expect(visited).not.toContain('/login');
    expect(router.state.location.pathname).toBe('/events/1');
    expect(queryClient.getQueryData(SESSION_QUERY_KEY)).toEqual({ role: 'viewer' });
    expect(setItem).not.toHaveBeenCalled();
    expect(takePendingLinkPassword()).toBeNull();
  });

  it('shows the normal loading state while the login resolves', async () => {
    server.use(
      loggedOut,
      http.post('/api/auth/link-login', async () => {
        await delay(30);
        return HttpResponse.json({ role: 'viewer' });
      }),
    );
    setup(`/events/1?p=${TEST_PASSWORDS.viewer}`);
    expect(screen.getByRole('status', { name: 'Checking your session' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Password')).toBeNull();
    expect(await screen.findByText('protected page')).toBeInTheDocument();
  });

  it('a wrong password lands on /login with the note and a clean next', async () => {
    server.use(loggedOut);
    const { router } = setup('/events/1?p=wrong-pw&rt=sporting');
    expect(
      await screen.findByText("That link's password didn't work. Enter the password to continue."),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/login');
    const search = router.state.location.search;
    expect(search).toBe('?next=%2Fevents%2F1%3Frt%3Dsporting');
    expect(search).not.toContain('wrong-pw');
    expect(document.body.textContent).not.toContain('wrong-pw');
  });

  it('an admin password in a link is just wrong', async () => {
    server.use(loggedOut);
    setup(`/events/1?p=${TEST_PASSWORDS.admin}`);
    expect(await screen.findByText(/link's password didn't work/)).toBeInTheDocument();
  });

  it('a rate limit gets the same path', async () => {
    server.use(
      loggedOut,
      http.post('/api/auth/link-login', () =>
        HttpResponse.json(
          { error: { code: 'rate_limited', message: 'Too many attempts' } },
          { status: 429 },
        ),
      ),
    );
    setup('/events/1?p=anything');
    expect(await screen.findByText(UNAVAILABLE_NOTE)).toBeInTheDocument();
    expect(screen.queryByText(/password didn't work/)).toBeNull();
  });

  it('a busy server says so, not that the password was wrong', async () => {
    server.use(
      loggedOut,
      http.post('/api/auth/link-login', () =>
        HttpResponse.json({ error: { code: 'login_busy', message: 'Busy' } }, { status: 429 }),
      ),
    );
    setup('/events/1?p=anything');
    expect(await screen.findByText(UNAVAILABLE_NOTE)).toBeInTheDocument();
  });

  it('a server error says the link could not be checked', async () => {
    server.use(
      loggedOut,
      http.post('/api/auth/link-login', () => HttpResponse.json({}, { status: 500 })),
    );
    setup('/events/1?p=anything');
    expect(await screen.findByText(UNAVAILABLE_NOTE)).toBeInTheDocument();
  });

  it('a network failure gets the could-not-check path without crashing', async () => {
    server.use(
      loggedOut,
      http.post('/api/auth/link-login', () => HttpResponse.error()),
    );
    const { router } = setup('/events/1?p=anything');
    expect(await screen.findByText(UNAVAILABLE_NOTE)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/login');
  });

  it.each(['viewer', 'admin'] as const)(
    'an existing %s session ignores the link, sends no login and keeps the role',
    async (role) => {
      server.use(http.get('/api/auth/me', () => HttpResponse.json({ role })));
      const bodies = spyLinkLogin();
      const { visited, queryClient } = setup(`/events/1?p=${TEST_PASSWORDS.viewer}&x=1`);
      expect(await screen.findByText('protected page')).toBeInTheDocument();
      expect(bodies).toEqual([]);
      expect(window.location.search).toBe('?x=1');
      expect(visited).not.toContain('/login');
      expect(queryClient.getQueryData(SESSION_QUERY_KEY)).toEqual({ role });
      expect(takePendingLinkPassword()).toBeNull();
    },
  );

  it('sends the login request only with the password in the body', async () => {
    server.use(loggedOut);
    const bodies = spyLinkLogin();
    setup('/events/1?p=my-fake-pw');
    expect(await screen.findByText('protected page')).toBeInTheDocument();
    expect(bodies).toEqual([{ password: 'my-fake-pw' }]);
  });

  it('drops the password without a login when the session check fails', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({}, { status: 503 })));
    const bodies = spyLinkLogin();
    const { queryClient } = setup('/events/1?p=my-fake-pw');
    await waitFor(() => expect(queryClient.isFetching()).toBe(0));
    await screen.findByText("Can't reach the server");
    expect(bodies).toEqual([]);
    expect(takePendingLinkPassword()).toBeNull();
    expect(queryClient.getQueryData(LINK_FAILED_KEY)).toBe('unavailable');
  });

  it('does not update state when unmounted before the login settles', async () => {
    server.use(
      loggedOut,
      http.post('/api/auth/link-login', async () => {
        await delay(30);
        return HttpResponse.json({ role: 'viewer' });
      }),
    );
    const { unmount, queryClient } = setup('/events/1?p=my-fake-pw');
    unmount();
    await waitFor(() =>
      expect(queryClient.getQueryData(SESSION_QUERY_KEY)).toEqual({ role: 'viewer' }),
    );
    expect(screen.queryByText('protected page')).toBeNull();
  });

  it('renders straight away when the URL had no link password', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({ role: 'viewer' })));
    const bodies = spyLinkLogin();
    setup('/events/1?x=1');
    expect(await screen.findByText('protected page')).toBeInTheDocument();
    expect(bodies).toEqual([]);
  });
});
