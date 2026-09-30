import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderRoutes } from '../../../test/render';
import { TEST_PASSWORDS } from '../mocks';
import { LoginPage } from './LoginPage';

const ROUTES = [
  { path: '/login', element: <LoginPage /> },
  { path: '*', element: <p>app</p> },
];

function renderLogin(search = '') {
  return renderRoutes(ROUTES, { route: `/login${search}`, role: null });
}

describe('LoginPage', () => {
  it('keeps the submit button disabled until a password is typed', async () => {
    const { user } = renderLogin();
    const submit = screen.getByRole('button', { name: 'Log in' });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText('Password'), 'x');
    expect(submit).toBeEnabled();
  });

  it('shows "Wrong password." for a rejected password and stays on the page', async () => {
    const { user, router } = renderLogin('?next=%2Fexplorer');
    await user.type(screen.getByLabelText('Password'), 'nope');
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong password.');
    expect(router.state.location.pathname).toBe('/login');
  });

  it('focuses the password field when the page opens', () => {
    renderLogin();
    expect(screen.getByLabelText('Password')).toHaveFocus();
  });

  it('marks the field invalid, links it to the error and returns focus to it after a failure', async () => {
    const { user } = renderLogin();
    const input = screen.getByLabelText('Password');
    expect(input).not.toHaveAttribute('aria-invalid');
    expect(input).not.toHaveAttribute('aria-describedby');
    await user.type(input, 'nope');
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong password.');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAccessibleDescription('Wrong password.');
    await waitFor(() => {
      expect(input).toHaveFocus();
    });
  });

  it('explains the rate limit on 429', async () => {
    server.use(
      http.post('/api/auth/login', () =>
        HttpResponse.json(
          { error: { code: 'rate_limited', message: 'Too many failed logins. Try again later.' } },
          { status: 429 },
        ),
      ),
    );
    const { user } = renderLogin();
    await user.type(screen.getByLabelText('Password'), 'x');
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts');
  });

  it('asks to retry shortly when the server is busy (429 login_busy), not "too many attempts"', async () => {
    server.use(
      http.post('/api/auth/login', () =>
        HttpResponse.json(
          { error: { code: 'login_busy', message: 'The server is busy. Try again in a moment.' } },
          { status: 429 },
        ),
      ),
    );
    const { user } = renderLogin();
    await user.type(screen.getByLabelText('Password'), 'x');
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The server is busy. Try again in a moment.',
    );
  });

  it('shows a connection message for other failures', async () => {
    server.use(http.post('/api/auth/login', () => HttpResponse.error()));
    const { user } = renderLogin();
    await user.type(screen.getByLabelText('Password'), 'x');
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not log in');
  });

  it('returns to next after a successful login (the ?next= round-trip)', async () => {
    const { user, router, queryClient } = renderLogin('?next=%2Fevents%2F2026-09-13%3Fx%3D1');
    await user.type(screen.getByLabelText('Password'), TEST_PASSWORDS.admin);
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByText('app')).toBeInTheDocument();
    expect(router.state.location.pathname + router.state.location.search).toBe(
      '/events/2026-09-13?x=1',
    );
    expect(router.state.historyAction).toBe('REPLACE');
    expect(queryClient.getQueryData(['/api/auth/me'])).toEqual({ role: 'admin' });
  });

  it("drops the previous session's cached data when someone logs in", async () => {
    const { user, queryClient } = renderLogin();
    queryClient.setQueryData(['/api/events'], ['from the previous session']);
    await user.type(screen.getByLabelText('Password'), TEST_PASSWORDS.viewer);
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByText('app')).toBeInTheDocument();
    expect(queryClient.getQueryData(['/api/events'])).toBeUndefined();
    expect(queryClient.getQueryData(['/api/auth/me'])).toEqual({ role: 'viewer' });
  });

  it('does not keep the password in the mutation cache once the page is left', async () => {
    const { user, queryClient } = renderLogin();
    await user.type(screen.getByLabelText('Password'), TEST_PASSWORDS.admin);
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByText('app')).toBeInTheDocument();
    await waitFor(() => {
      const variables = queryClient
        .getMutationCache()
        .getAll()
        .map((mutation) => mutation.state.variables);
      expect(variables).not.toContain(TEST_PASSWORDS.admin);
    });
  });

  it.each([
    ['//evil.com'],
    ['https%3A%2F%2Fevil.com'],
    ['%2F%0a%2Fevil.com'],
    ['%2F.%2F%2Fevil.com'],
  ])('never follows a hostile next=%s off the site', async (next) => {
    const { user, router } = renderLogin(`?next=${next}`);
    await user.type(screen.getByLabelText('Password'), TEST_PASSWORDS.viewer);
    await user.click(screen.getByRole('button', { name: 'Log in' }));
    expect(await screen.findByText('app')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/');
  });

  it('bounces an already signed-in visitor to next immediately', async () => {
    const { router } = renderRoutes(ROUTES, { route: '/login?next=%2Fclub', role: 'viewer' });
    expect(await screen.findByText('app')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/club');
  });
});
