import { e2ePassword } from './authState';
import { expect, test } from './fixtures';

// API-level auth checks; they start from an empty cookie jar, not the setup's storage state.
test.use({ storageState: { cookies: [], origins: [] } });

for (const role of ['viewer', 'admin'] as const) {
  test(`the ${role} password logs in as ${role}`, async ({ request }) => {
    const login = await request.post('/api/auth/login', { data: { password: e2ePassword(role) } });
    expect(login.status()).toBe(200);
    expect(await login.json()).toEqual({ role });
    const me = await request.get('/api/auth/me');
    expect(await me.json()).toEqual({ role });
  });
}

test('a wrong password is rejected with 401 and no session', async ({ request }) => {
  const login = await request.post('/api/auth/login', {
    data: { password: 'definitely-not-the-password' },
  });
  expect(login.status()).toBe(401);
  expect((await request.get('/api/auth/me')).status()).toBe(401);
});

test('logout clears the session cookie', async ({ request }) => {
  await request.post('/api/auth/login', { data: { password: e2ePassword('viewer') } });
  const logout = await request.post('/api/auth/logout');
  expect(logout.status()).toBe(204);
  expect((await request.get('/api/auth/me')).status()).toBe(401);
  const { cookies } = await request.storageState();
  expect(cookies.filter((cookie) => cookie.name === 'sc_session')).toEqual([]);
});
