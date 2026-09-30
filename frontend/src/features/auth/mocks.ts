import { http, HttpResponse } from 'msw';

/** Passwords accepted by the default MSW login handler. */
export const TEST_PASSWORDS = { viewer: 'viewer-pw', admin: 'admin-pw' } as const;

export const handlers = [
  http.get('/api/auth/me', () => HttpResponse.json({ role: 'viewer' })),
  http.post('/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as { password?: unknown };
    if (body.password === TEST_PASSWORDS.admin) return HttpResponse.json({ role: 'admin' });
    if (body.password === TEST_PASSWORDS.viewer) return HttpResponse.json({ role: 'viewer' });
    return HttpResponse.json(
      { error: { code: 'invalid_password', message: 'Wrong password' } },
      { status: 401 },
    );
  }),
  http.post('/api/auth/logout', () => new HttpResponse(null, { status: 204 })),
];
