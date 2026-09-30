import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../test/msw/server';
import { api, loginPath, setNavigate, shouldRedirectToLogin, unwrap } from './client';
import { ApiError } from './errors';

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('unwrap', () => {
  it('returns the data of a 2xx response from a same-origin relative path', async () => {
    server.use(http.get('/api/health', () => HttpResponse.json({ status: 'ok', version: 'test' })));
    await expect(unwrap(api.GET('/api/health'))).resolves.toEqual({
      status: 'ok',
      version: 'test',
    });
  });

  it('throws ApiError carrying the server code and message', async () => {
    server.use(
      http.get('/api/health', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    const error: unknown = await unwrap(api.GET('/api/health')).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 500,
      code: 'internal',
      message: 'Internal server error',
    });
  });

  it('lets a network failure through unchanged as the fetch TypeError', async () => {
    server.use(http.get('/api/health', () => HttpResponse.error()));
    const error: unknown = await unwrap(api.GET('/api/health')).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(TypeError);
    expect(error).not.toBeInstanceOf(ApiError);
  });
});

describe('401 handling', () => {
  it.each([
    [401, '/api/health', '/events', true],
    [401, '/api/auth/me', '/events', false],
    [401, '/api/auth/login', '/login', false],
    [401, '/api/auth/logout', '/', false],
    [401, '/api/health', '/login', false],
    [403, '/api/health', '/events', false],
  ])('status %s from %s on page %s redirects: %s', (status, schemaPath, pathname, expected) => {
    expect(shouldRedirectToLogin(status, schemaPath, pathname)).toBe(expected);
  });

  it('builds next only from pathname + search', () => {
    window.history.replaceState(null, '', '/explorer?m=score&g=year#chart');
    expect(loginPath()).toBe('/login?next=%2Fexplorer%3Fm%3Dscore%26g%3Dyear');
  });

  it('sends an expired session on a data request to the login page with next', async () => {
    const navigate = vi.fn();
    setNavigate(navigate);
    window.history.replaceState(null, '', '/events/2026-09-13?rt=sporting');
    server.use(
      http.get('/api/health', () =>
        HttpResponse.json({ error: { code: 'unauthenticated', message: 'x' } }, { status: 401 }),
      ),
    );
    await expect(unwrap(api.GET('/api/health'))).rejects.toMatchObject({ status: 401 });
    expect(navigate).toHaveBeenCalledWith('/login?next=%2Fevents%2F2026-09-13%3Frt%3Dsporting');
  });

  it('falls back to a full page load until App.tsx installs router navigation', async () => {
    vi.resetModules();
    const fresh = await import('./client');
    const assign = vi.fn();
    // jsdom's location.assign cannot be spied on (unforgeable) and jsdom does not navigate, so the
    // page's location is replaced by a plain object; MSW resolves handler paths against its href.
    const page = new URL('/events?rt=sporting', window.location.origin);
    const { href, origin, pathname, search } = page;
    vi.stubGlobal('location', { href, origin, pathname, search, assign });
    server.use(
      http.get('/api/health', () =>
        HttpResponse.json({ error: { code: 'unauthenticated', message: 'x' } }, { status: 401 }),
      ),
    );
    await expect(fresh.unwrap(fresh.api.GET('/api/health'))).rejects.toMatchObject({
      status: 401,
    });
    expect(assign).toHaveBeenCalledWith('/login?next=%2Fevents%3Frt%3Dsporting');
  });
});
