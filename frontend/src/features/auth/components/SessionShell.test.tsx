import { act, screen, waitFor } from '@testing-library/react';
import { Compass } from 'lucide-react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { NavItem } from '../../../app/registry';
import { resetMeForTests } from '../../../lib/me';
import { server } from '../../../test/msw/server';
import { renderRoutes } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { SESSION_QUERY_KEY } from '../api';
import { RequireRole } from './RequireRole';
import { SessionShell } from './SessionShell';

// A launch-switched nav item: no real page is gated yet, so the registry gains a test one.
vi.mock('../../../app/registry', async (importOriginal) => {
  const actual = await importOriginal<{ navItems: NavItem[] }>();
  const gated: NavItem = {
    label: 'Gated page',
    path: '/gated',
    icon: Compass,
    order: 135,
    feature: 'summary_card',
  };
  return { ...actual, navItems: [...actual.navItems, gated] };
});

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

const PAGE_ROUTES = [
  {
    path: '/',
    element: (
      <RequireRole>
        <SessionShell />
      </RequireRole>
    ),
    children: [
      { index: true, element: <p>home page</p> },
      { path: 'shooters/:id', element: <p>profile page</p> },
    ],
  },
];

describe('SessionShell page views', () => {
  function capture(): unknown[] {
    const sent: unknown[] = [];
    server.use(
      http.post('*/api/pageviews', async ({ request }) => {
        sent.push(await request.json());
        return new HttpResponse(null, { status: 204 });
      }),
    );
    return sent;
  }

  afterEach(() => {
    resetMeForTests();
    localStorage.clear();
  });

  it('sends one beacon per page for a viewer and none for a query-only change', async () => {
    stubViewport('desktop');
    const sent = capture();
    const kinds = () => sent.map((b) => (b as { page_kind: string }).page_kind);
    const { router } = renderRoutes(PAGE_ROUTES, { route: '/', role: 'viewer' });
    await waitFor(() => expect(sent).toHaveLength(1));
    await act(() => router.navigate('/shooters/3'));
    await waitFor(() => expect(sent).toHaveLength(2));
    await act(() => router.navigate('/shooters/3?w=12m'));
    // Then a real page change: its beacon is pushed after any stray one for the query change
    // (the handler pushes in order), so waiting for it proves no beacon was sent for `?w=12m`.
    await act(() => router.navigate('/'));
    await waitFor(() => expect(sent.length).toBeGreaterThanOrEqual(3));
    expect(kinds()).toEqual(['home', 'profile', 'home']);
  });

  it('sends nothing for an admin session', async () => {
    stubViewport('desktop');
    const sent = capture();
    const { router } = renderRoutes(PAGE_ROUTES, { route: '/', role: 'admin' });
    await screen.findByText('home page');
    await act(() => router.navigate('/shooters/3'));
    await screen.findByText('profile page');
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(sent).toEqual([]);
  });
});

describe('SessionShell launch switches', () => {
  const off = () =>
    server.use(http.get('*/api/features', () => HttpResponse.json({ switches: {} })));

  it('lists a gated nav item for an admin while its switch is off', async () => {
    stubViewport('desktop');
    off();
    renderRoutes(ROUTES, { route: '/', role: 'admin' });
    expect(await screen.findByRole('link', { name: 'Gated page' })).toBeInTheDocument();
  });

  it('hides a gated nav item from a viewer while its switch is off', async () => {
    stubViewport('desktop');
    off();
    renderRoutes(ROUTES, { route: '/', role: 'viewer' });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(screen.queryByRole('link', { name: 'Gated page' })).not.toBeInTheDocument();
  });

  it('lists a gated nav item for a viewer once its switch is on', async () => {
    stubViewport('desktop');
    server.use(
      http.get('*/api/features', () => HttpResponse.json({ switches: { summary_card: true } })),
    );
    renderRoutes(ROUTES, { route: '/', role: 'viewer' });
    expect(await screen.findByRole('link', { name: 'Gated page' })).toBeInTheDocument();
  });
});
