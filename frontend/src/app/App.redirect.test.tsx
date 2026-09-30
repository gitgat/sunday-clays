import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { api, unwrap } from '../api/client';
import { server } from '../test/msw/server';
// Importing App installs its router as the 401 navigation target (setNavigate).
import './App';

afterEach(() => {
  window.history.replaceState(null, '', '/');
});

describe('App 401 wiring', () => {
  it('sends a data request 401 through the app router to the login page with next', async () => {
    window.history.replaceState(null, '', '/?rt=sporting');
    server.use(
      http.get('/api/health', () =>
        HttpResponse.json({ error: { code: 'unauthenticated', message: 'x' } }, { status: 401 }),
      ),
    );
    await expect(unwrap(api.GET('/api/health'))).rejects.toMatchObject({ status: 401 });
    await vi.waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe(
        '/login?next=%2F%3Frt%3Dsporting',
      );
    });
  });
});
