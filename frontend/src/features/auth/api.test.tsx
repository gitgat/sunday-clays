import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../test/msw/server';
import { fetchSession } from './api';

describe('fetchSession', () => {
  it('returns the role for a signed-in session', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({ role: 'admin' })));
    await expect(fetchSession()).resolves.toEqual({ role: 'admin' });
  });

  it('returns null when logged out (401) without redirecting', async () => {
    server.use(
      http.get('/api/auth/me', () =>
        HttpResponse.json(
          { error: { code: 'unauthenticated', message: 'Log in to continue' } },
          { status: 401 },
        ),
      ),
    );
    await expect(fetchSession()).resolves.toBeNull();
  });

  it('throws on a server failure instead of pretending to be logged out', async () => {
    server.use(http.get('/api/auth/me', () => HttpResponse.json({}, { status: 503 })));
    await expect(fetchSession()).rejects.toMatchObject({ status: 503 });
  });
});
